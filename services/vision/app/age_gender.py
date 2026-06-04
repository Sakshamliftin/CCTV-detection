import random
from typing import Tuple

class AgeGenderPredictor:
    """
    Lightweight age/gender classifier.
    In a real app, uses DeepFace or InsightFace.
    For this challenge, using a deterministic assignment based on track_id
    so that results are stable across frames for the same person.
    """
    
    @staticmethod
    def predict(track_id: int) -> Tuple[str, int, str]:
        """Returns (gender, age, age_bucket)"""
        # Deterministic pseudo-random based on track_id
        random.seed(track_id)
        
        gender = random.choice(["M", "F"])
        age = random.randint(18, 65)
        
        if age < 25:
            bucket = "18-24"
        elif age < 35:
            bucket = "25-34"
        elif age < 45:
            bucket = "35-44"
        elif age < 55:
            bucket = "45-54"
        else:
            bucket = "55+"
            
        return gender, age, bucket
