import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from yt_dlp import YoutubeDL
from moviepy.video.io.VideoFileClip import VideoFileClip

app = FastAPI()

# السماح للواجهة بالاتصال بالسيرفر بدون حظر (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProcessRequest(BaseModel):
    youtube_url: str
    api_key: str

@app.get("/")
def home():
    return {"message": "Crayo Backend Server is Running Free!"}

@app.post("/process")
def process_video(req: ProcessRequest):
    try:
        # 1. إعداد عميل Gemini
        client = genai.Client(api_key=req.api_key)
        
        # 2. تحميل الفيديو
        video_filename = "downloaded_video.mp4"
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]',
            'outtmpl': video_filename,
            'quiet': True
        }
        
        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([req.youtube_url])
            
        # 3. رفع الفيديو للذكاء الاصطناعي وتحليله
        video_file = client.files.upload(file=video_filename)
        prompt = """
        Analyze this video completely and extract the top 3 most engaging, viral-worthy clips suitable for Shorts/Reels.
        Each clip must be between 30 to 60 seconds in duration.
        
        Format output strictly as:
        CLIP_START: [start timestamp in total seconds]
        CLIP_END: [end timestamp in total seconds]
        ---
        """
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[video_file, prompt]
        )
        
        # 4. استخراج التوقيتات وقص الفيديو
        matches = re.findall(r"CLIP_START:\s*(\d+)\s*CLIP_END:\s*(\d+)", response.text)
        
        if not matches:
            raise Exception("لم يتمكن الذكاء الاصطناعي من قراءة التوقيتات بشكل صحيح.")
            
        video = VideoFileClip(video_filename)
        output_files = []
        
        for idx, (start, end) in enumerate(matches[:3]):
            start_sec = int(start)
            end_sec = int(end)
            output_name = f"clip_{idx+1}.mp4"
            
            new_clip = video.subclip(start_sec, end_sec)
            new_clip.write_videofile(output_name, codec="libx264", audio_codec="aac", verbose=False, logger=None)
            output_files.append(output_name)
            
        video.close()
        return {"status": "success", "files": output_files}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
