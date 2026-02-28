# Download and cache ONNX face detection/recognition models for insightface
import insightface

# Download face detection and recognition models (first run will cache them)
def download_models():
    print("Downloading face detection model...")
    detector = insightface.model_zoo.get_model('buffalo_l')
    detector.prepare(ctx_id=-1)
    print("Models downloaded and ready.")

if __name__ == "__main__":
    download_models()
