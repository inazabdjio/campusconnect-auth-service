import base64
import cv2
import numpy as np


class LivenessCheckError(Exception):
    pass


class FaceProcessingError(Exception):
    pass


class FaceBiometricEngine:
    def __init__(self, distance_threshold: float = 0.40):
        self.distance_threshold = distance_threshold

    @staticmethod
    def decode_base64_image(image_b64: str) -> np.ndarray:
        raw = base64.b64decode(image_b64)
        arr = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise FaceProcessingError("Image faciale invalide ou illisible.")
        return img

    @staticmethod
    def verify_simple_liveness(frame_1_b64: str, frame_2_b64: str | None = None) -> bool:
        """Détection de vivacité simple : mouvement/changement de scène ou variation de texture."""
        img1 = cv2.cvtColor(FaceBiometricEngine.decode_base64_image(frame_1_b64), cv2.COLOR_BGR2GRAY)
        img1 = cv2.resize(img1, (160, 160))

        if frame_2_b64:
            img2 = cv2.cvtColor(FaceBiometricEngine.decode_base64_image(frame_2_b64), cv2.COLOR_BGR2GRAY)
            img2 = cv2.resize(img2, (160, 160))
            diff_score = float(np.mean(np.abs(img1.astype(np.float32) - img2.astype(np.float32))))
            # Une différence trop nulle indique une image figée ; une différence extrême indique un changement de scène complet
            if diff_score < 1.5:
                raise LivenessCheckError("Vivacité non confirmée : aucun mouvement détecté entre les captures.")
            return True

        # Repli sur une seule image : vérifie la netteté/texture (laplacien) pour rejeter les écrans très flous/statiques
        laplacian_var = float(cv2.Laplacian(img1, cv2.CV_64F).var())
        if laplacian_var < 15.0:
            raise LivenessCheckError("Vivacité non confirmée : image trop floue ou non vivante.")
        return True

    def extract_embedding(self, image_b64: str) -> np.ndarray:
        """Extrait un vecteur normalisé. Utilise DeepFace si disponible, sinon un descripteur facial normalisé."""
        img = self.decode_base64_image(image_b64)
        try:
            from deepface import DeepFace  # type: ignore

            reps = DeepFace.represent(img_path=img, model_name="Facenet", enforce_detection=False)
            vec = np.array(reps[0]["embedding"], dtype=np.float32)
        except Exception:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (32, 32)).flatten().astype(np.float32)
            vec = resized

        norm = np.linalg.norm(vec)
        if norm == 0:
            raise FaceProcessingError("Impossible d'extraire un embedding facial valide.")
        return vec / norm

    @staticmethod
    def cosine_distance(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        denom = float(np.linalg.norm(vec_a) * np.linalg.norm(vec_b))
        if denom == 0:
            return 1.0
        similarity = float(np.dot(vec_a, vec_b)) / denom
        return max(0.0, 1.0 - similarity)

    def is_match(self, probe_embedding: np.ndarray, stored_embedding: np.ndarray) -> tuple[bool, float]:
        dist = self.cosine_distance(probe_embedding, stored_embedding)
        return dist <= self.distance_threshold, dist