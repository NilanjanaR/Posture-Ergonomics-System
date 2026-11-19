# posture.py
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import math
import os

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'pose_landmarker_lite.task')

def calculate_angle(a, b, c):
    angle_rad = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0])
    angle_deg = abs(math.degrees(angle_rad))
    if angle_deg > 180: 
        angle_deg = 360 - angle_deg
    return angle_deg

def analyze_posture(image_path):
    if not os.path.exists(MODEL_PATH):
        return {"error": "AI model file not found."}

    image = cv2.imread(image_path)
    if image is None:
        return {"error": "Image not found."}
        
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        min_pose_detection_confidence=0.5
    )
    
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        detection_result = landmarker.detect(mp_image)
        
        if not detection_result.pose_landmarks:
            return {"error": "No human detected in the image."}
        
        landmarks = detection_result.pose_landmarks[0]
        
        # අවශ්‍ය ලක්ෂ්‍ය
        nose = [landmarks[0].x, landmarks[0].y]
        left_ear = [landmarks[7].x, landmarks[7].y]
        left_shoulder = [landmarks[11].x, landmarks[11].y]
        right_shoulder = [landmarks[12].x, landmarks[12].y]
        left_hip = [landmarks[23].x, landmarks[23].y]
        
        issues = []
        score = 100
        
        # ==========================================
        # ලෙක්චරර්ගේ Feedback එකට අනුව හදපු අලුත් Scoring Logic එක
        # ==========================================
        
        # 1. Forward Head Position (ඔළුව ඉස්සරහට යාම) - 15 ලකුණු අඩු කරයි
        neck_angle = calculate_angle(left_ear, left_shoulder, left_hip)
        
        # කෝණය 165ට අඩු නම් හෝ ඔළුව උරහිසට වඩා ගොඩක් ඉස්සරහට තියෙනවා නම්
        if neck_angle < 165 or (nose[0] - left_shoulder[0]) > 0.08:
            issues.append("Forward Head Position")
            score -= 15 
            
        # 2. Slouching (ඇඟ නමා ඉඳීම) - 20 ලකුණු අඩු කරයි
        if abs(left_shoulder[0] - left_hip[0]) > 0.05:
            issues.append("Slouching")
            score -= 20
            
        # 3. Uneven Shoulders (උරහිස් අසමාන වීම) - 10 ලකුණු අඩු කරයි
        if abs(left_shoulder[1] - right_shoulder[1]) > 0.03:
            issues.append("Uneven Shoulders")
            score -= 10

        # අවුල් 2ක් හෝ 3ක් තියෙනවා නම් තව ලකුණු 10ක් අඩු කරමු
        if len(issues) >= 2:
            score -= 10
            
        score = max(0, score)
        
        # ==========================================
        # Status එක තීරණය කිරීම (හැම තත්ත්වයකටම ගැලපෙන විදිහට)
        # ==========================================
        if score >= 85: 
            status = "Good"
        elif score >= 50: 
            status = "Needs Attention"
        else: 
            status = "Poor"
            
        return {
            "success": True,
            "score": score,
            "status": status,
            "issues": issues
        }