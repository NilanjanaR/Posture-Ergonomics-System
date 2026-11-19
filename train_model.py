# train_model.py
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import math
import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

MODEL_PATH = 'pose_landmarker_lite.task'
DATASET_DIR = 'dataset'
CSV_FILE = 'posture_data.csv'

def calculate_angle(a, b, c):
    angle_rad = math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(a[1] - b[1], a[0] - b[0])
    angle_deg = abs(math.degrees(angle_rad))
    if angle_deg > 180: angle_deg = 360 - angle_deg
    return angle_deg

def extract_features():
    data = []
    labels = []
    
    base_options = python.BaseOptions(model_asset_path=MODEL_PATH)
    options = vision.PoseLandmarkerOptions(base_options=base_options, running_mode=vision.RunningMode.IMAGE)
    
    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        for label_name in ['good_posture', 'forward_head', 'slouching']:
            folder_path = os.path.join(DATASET_DIR, label_name)
            if not os.path.exists(folder_path):
                print(f"Folder not found: {folder_path}")
                continue
                
            print(f"Processing folder: {label_name}...")
            for img_name in os.listdir(folder_path):
                img_path = os.path.join(folder_path, img_name)
                image = cv2.imread(img_path)
                if image is None: continue
                
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
                detection_result = landmarker.detect(mp_image)
                
                if detection_result.pose_landmarks:
                    landmarks = detection_result.pose_landmarks[0]
                    
                    left_ear = [landmarks[7].x, landmarks[7].y]
                    left_shoulder = [landmarks[11].x, landmarks[11].y]
                    right_shoulder = [landmarks[12].x, landmarks[12].y]
                    left_hip = [landmarks[23].x, landmarks[23].y]
                    nose = [landmarks[0].x, landmarks[0].y]
                    
                    # Features 4ක් ගන්නවා
                    neck_angle = calculate_angle(left_ear, left_shoulder, left_hip)
                    shoulder_diff = abs(left_shoulder[1] - right_shoulder[1])
                    nose_to_shoulder_x = abs(nose[0] - left_shoulder[0])
                    ear_to_shoulder_x = abs(left_ear[0] - left_shoulder[0])
                    
                    data.append([neck_angle, shoulder_diff, nose_to_shoulder_x, ear_to_shoulder_x])
                    labels.append(label_name)
                    
    df = pd.DataFrame(data, columns=['neck_angle', 'shoulder_diff', 'nose_to_shoulder_x', 'ear_to_shoulder_x'])
    df['label'] = labels
    df.to_csv(CSV_FILE, index=False)
    print(f"Data extracted and saved to {CSV_FILE}! Total records: {len(data)}")

def train():
    print("Extracting data from images...")
    extract_features()
    
    print("Training model...")
    df = pd.read_csv(CSV_FILE)
    
    if len(df) == 0:
        print("Error: No data found. Please add images to the dataset folders.")
        return
        
    X = df[['neck_angle', 'shoulder_diff', 'nose_to_shoulder_x', 'ear_to_shoulder_x']]
    y = df['label']
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    predictions = model.predict(X_test)
    print(f"Model Accuracy: {accuracy_score(y_test, predictions) * 100:.2f}%")
    
    joblib.dump(model, 'posture_model.pkl')
    print("Model saved as posture_model.pkl!")

# මේක අනිවාර්යයෙන්ම තියෙන්න ඕනේ
if __name__ == '__main__':
    train()