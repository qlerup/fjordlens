import AVFoundation
import AVKit
import Capacitor
import UIKit

@objc(FjordLensAirPlayPlugin)
public final class FjordLensAirPlayPlugin: CAPPlugin, CAPBridgedPlugin {
    public let identifier = "FjordLensAirPlayPlugin"
    public let jsName = "FjordLensAirPlay"
    public let pluginMethods: [CAPPluginMethod] = [
        CAPPluginMethod(name: "start", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "stop", returnType: CAPPluginReturnPromise),
        CAPPluginMethod(name: "status", returnType: CAPPluginReturnPromise),
    ]

    private var player: AVPlayer?
    private weak var playerController: FjordLensAirPlayViewController?
    private var externalPlaybackObservation: NSKeyValueObservation?

    @objc public func start(_ call: CAPPluginCall) {
        guard let urlString = call.getString("url"),
              let url = URL(string: urlString),
              ["https", "http"].contains(url.scheme?.lowercased() ?? "") else {
            call.reject("Ugyldig AirPlay/HLS URL.")
            return
        }
        let title = call.getString("title") ?? "FjordLens"

        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.dismissCurrentPlayer(animated: false)

            do {
                let session = AVAudioSession.sharedInstance()
                try session.setCategory(.playback, mode: .moviePlayback, options: [.allowAirPlay])
                try session.setActive(true)
            } catch {
                call.reject("Kunne ikke aktivere AirPlay-lyd: \(error.localizedDescription)")
                return
            }

            let item = AVPlayerItem(url: url)
            item.preferredForwardBufferDuration = 8
            let player = AVPlayer(playerItem: item)
            player.allowsExternalPlayback = true
            player.usesExternalPlaybackWhileExternalScreenIsActive = true
            player.automaticallyWaitsToMinimizeStalling = true
            self.player = player

            let controller = FjordLensAirPlayViewController(player: player, titleText: title)
            controller.modalPresentationStyle = .fullScreen
            controller.onClose = { [weak self] in
                self?.notifyListeners("closed", data: [:])
                self?.cleanupPlayer()
            }
            self.playerController = controller

            self.externalPlaybackObservation = player.observe(\.isExternalPlaybackActive, options: [.initial, .new]) { [weak self] player, _ in
                DispatchQueue.main.async {
                    self?.notifyListeners("externalPlaybackChanged", data: [
                        "active": player.isExternalPlaybackActive,
                    ])
                }
            }

            guard let host = self.bridge?.viewController else {
                self.cleanupPlayer()
                call.reject("Capacitor view controller er ikke tilgængelig.")
                return
            }
            host.present(controller, animated: true) {
                player.play()
                call.resolve([
                    "started": true,
                    "externalPlaybackActive": player.isExternalPlaybackActive,
                ])
            }
        }
    }

    @objc public func stop(_ call: CAPPluginCall) {
        DispatchQueue.main.async { [weak self] in
            self?.dismissCurrentPlayer(animated: true)
            call.resolve(["stopped": true])
        }
    }

    @objc public func status(_ call: CAPPluginCall) {
        DispatchQueue.main.async { [weak self] in
            guard let player = self?.player else {
                call.resolve(["playing": false, "externalPlaybackActive": false])
                return
            }
            call.resolve([
                "playing": player.timeControlStatus == .playing,
                "externalPlaybackActive": player.isExternalPlaybackActive,
            ])
        }
    }

    private func dismissCurrentPlayer(animated: Bool) {
        if let controller = playerController, controller.presentingViewController != nil {
            controller.dismiss(animated: animated)
        }
        cleanupPlayer()
    }

    private func cleanupPlayer() {
        externalPlaybackObservation?.invalidate()
        externalPlaybackObservation = nil
        player?.pause()
        player?.replaceCurrentItem(with: nil)
        player = nil
        playerController = nil
        do {
            try AVAudioSession.sharedInstance().setActive(false, options: [.notifyOthersOnDeactivation])
        } catch {
            // Playback cleanup is best-effort.
        }
    }
}

private final class FjordLensAirPlayViewController: UIViewController {
    let player: AVPlayer
    let titleText: String
    var onClose: (() -> Void)?

    private let avController = AVPlayerViewController()
    private let routePicker = AVRoutePickerView(frame: .zero)
    private let titleLabel = UILabel()
    private let closeButton = UIButton(type: .system)

    init(player: AVPlayer, titleText: String) {
        self.player = player
        self.titleText = titleText
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black

        let topBar = UIView()
        topBar.backgroundColor = UIColor.black.withAlphaComponent(0.82)
        topBar.translatesAutoresizingMaskIntoConstraints = false

        titleLabel.text = titleText
        titleLabel.textColor = .white
        titleLabel.font = .systemFont(ofSize: 16, weight: .semibold)
        titleLabel.lineBreakMode = .byTruncatingMiddle
        titleLabel.translatesAutoresizingMaskIntoConstraints = false

        closeButton.setTitle("Luk", for: .normal)
        closeButton.setTitleColor(.white, for: .normal)
        closeButton.titleLabel?.font = .systemFont(ofSize: 16, weight: .semibold)
        closeButton.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
        closeButton.translatesAutoresizingMaskIntoConstraints = false

        routePicker.prioritizesVideoDevices = true
        routePicker.tintColor = .white
        routePicker.activeTintColor = .systemTeal
        routePicker.translatesAutoresizingMaskIntoConstraints = false
        routePicker.accessibilityLabel = "AirPlay"

        addChild(avController)
        avController.player = player
        avController.showsPlaybackControls = true
        avController.allowsPictureInPicturePlayback = false
        avController.view.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(avController.view)
        avController.didMove(toParent: self)

        view.addSubview(topBar)
        topBar.addSubview(closeButton)
        topBar.addSubview(titleLabel)
        topBar.addSubview(routePicker)

        NSLayoutConstraint.activate([
            topBar.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor),
            topBar.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            topBar.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            topBar.heightAnchor.constraint(equalToConstant: 58),

            closeButton.leadingAnchor.constraint(equalTo: topBar.leadingAnchor, constant: 14),
            closeButton.centerYAnchor.constraint(equalTo: topBar.centerYAnchor),
            closeButton.widthAnchor.constraint(greaterThanOrEqualToConstant: 48),

            routePicker.trailingAnchor.constraint(equalTo: topBar.trailingAnchor, constant: -14),
            routePicker.centerYAnchor.constraint(equalTo: topBar.centerYAnchor),
            routePicker.widthAnchor.constraint(equalToConstant: 44),
            routePicker.heightAnchor.constraint(equalToConstant: 44),

            titleLabel.leadingAnchor.constraint(equalTo: closeButton.trailingAnchor, constant: 10),
            titleLabel.trailingAnchor.constraint(equalTo: routePicker.leadingAnchor, constant: -10),
            titleLabel.centerYAnchor.constraint(equalTo: topBar.centerYAnchor),

            avController.view.topAnchor.constraint(equalTo: topBar.bottomAnchor),
            avController.view.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            avController.view.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            avController.view.bottomAnchor.constraint(equalTo: view.bottomAnchor),
        ])
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        UIApplication.shared.isIdleTimerDisabled = true
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        UIApplication.shared.isIdleTimerDisabled = false
    }

    @objc private func closeTapped() {
        dismiss(animated: true) { [weak self] in
            self?.onClose?()
        }
    }
}
