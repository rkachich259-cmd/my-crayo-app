import os
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from yt_dlp import YoutubeDL
from moviepy.video.io.VideoFileClip import VideoFileClip

app = FastAPI()

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
        client = genai.Client(api_key=req.api_key)
        video_filename = "downloaded_video.mp4"
        
        ydl_opts = {
            'format': 'best',
            'outtmpl': video_filename,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web']
                }
            }
        }

        with YoutubeDL(ydl_opts) as ydl:
            ydl.download([req.youtube_url])

        video_file = client.files.upload(file=video_filename)
        prompt = "Analyze this video completely and extract the top 3 most engaging clips. Each clip must be between 30 to 60 seconds. Provide timestamp intervals in start_time-end_time format."

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[video_file, prompt]
        )

        timestamps = re.findall(r'(\d+:\d+|\d+)-(\d+:\d+|\d+)', response.text)
        
        def to_sec(ts):
            parts = list(map(int, ts.split(':')))
            return parts[0] * 60 + parts[1] if len(parts) == 2 else parts[0]

        output_files = []
        with VideoFileClip(video_filename) as video:
            for i, (start, end) in enumerate(timestamps[:3]):
                s_sec, e_sec = to_sec(start), to_sec(end)
                clip = video.subclip(s_sec, e_sec)
                out_path = f"clip_{i+1}.mp4"
                clip.write_videofile(out_path, codec="libx264", audio_codec="aac")
                output_files.append(out_path)

        return {"status": "success", "clips": output_files}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
