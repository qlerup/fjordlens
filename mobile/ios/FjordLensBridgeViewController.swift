import Capacitor

final class FjordLensBridgeViewController: CAPBridgeViewController {
    override func capacitorDidLoad() {
        super.capacitorDidLoad()
        bridge?.registerPluginInstance(FjordLensAirPlayPlugin())
    }
}
