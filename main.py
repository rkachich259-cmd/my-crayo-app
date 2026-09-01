import os
import re
import shutil
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google import genai
from moviepy.editor import VideoFileClip

app = FastAPI()

# السماح للواجهة بالاتصال بالسيرفر بدون قيود CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# إنشاء مجلد حفظ الكليبات الناتجة
CLIPS_DIR = "static/clips"
os.makedirs(CLIPS_DIR, exist_ok=True)

# إتاحة المجلد كـ Static Files لتمكين التحميل والمعاينة المباشرة
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def home():
    return {"message": "Crayo Video Uploader & Clipper Server is Ready!"}

def parse_time_to_seconds(time_str: str) -> float:
    """تحويل التوقيت من صيغة MM:SS أو HH:MM:SS إلى ثوانٍ"""
    parts = list(map(float, time_str.split(":")))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return parts[0]

@app.post("/process")
async def process_video(
    file: UploadFile = File(...),
    api_key: str = Form(...)
):
    upload_path = f"temp_{file.filename}"
    try:
        # 1. حفظ ملف الفيديو المرفوع مؤقتاً
        with open(upload_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 2. رفع الفيديو إلى Gemini API لتحليله
        client = genai.Client(api_key=api_key)
        gemini_file = client.files.upload(file=upload_path)

        prompt = (
            "Analyze this video and extract the top 3 most engaging viral clips (30 to 60 seconds long). "
            "Return timestamp intervals in the exact format: MM:SS-MM:SS. "
            "Output each clip on a new line like: CLIP 1: 00:15-00:45"
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[gemini_file, prompt]
        )

        # 3. استخراج التوقيتات باستخدام Regex
        matches = re.findall(r'(\d+:\d+(?::\d+)?)\s*-\s*(\d+:\d+(?::\d+)?)', response.text)

        generated_clips = []

        if matches:
            video_clip = VideoFileClip(upload_path)
            duration = video_clip.duration

            for idx, (start_str, end_str) in enumerate(matches[:3]):
                start_sec = min(parse_time_to_seconds(start_str), duration - 1)
                end_sec = min(parse_time_to_seconds(end_str), duration)

                if end_sec <= start_sec:
                    continue

                # قص الفيديو
                sub = video_clip.subclip(start_sec, end_sec)
                out_name = f"clip_{idx+1}_{os.urandom(3).hex()}.mp4"
                out_path = os.path.join(CLIPS_DIR, out_name)

                sub.write_videofile(
                    out_path,
                    codec="libx264",
                    audio_codec="aac",
                    logger=None
                )

                generated_clips.append({
                    "title": f"الكليب {idx + 1}",
                    "time": f"{start_str} - {end_str}",
                    "url": f"/static/clips/{out_name}"
                })

            video_clip.close()

        # مسح الملف المؤقت الرئيسي
        if os.path.exists(upload_path):
            os.remove(upload_path)

        return {
            "status": "success",
            "clips": generated_clips,
            "raw_analysis": response.text
        }

    except Exception as e:
        if os.path.exists(upload_path):
            os.remove(upload_path)
        raise HTTPException(status_code=500, detail=str(e))
