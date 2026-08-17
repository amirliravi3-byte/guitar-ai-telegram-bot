from __future__ import annotations
import os, json
from pathlib import Path
import requests

class TelegramBot:
    def __init__(self, token=None):
        self.token=token or os.environ["TELEGRAM_BOT_TOKEN"]
        self.base=f"https://api.telegram.org/bot{self.token}"

    def get_file(self,file_id):
        r=requests.get(f"{self.base}/getFile",params={"file_id":file_id},timeout=30)
        r.raise_for_status()
        data=r.json()
        if not data.get("ok"): raise RuntimeError(data)
        return data["result"]

    def download(self,file_id,dest):
        info=self.get_file(file_id)
        path=info["file_path"]
        url=f"https://api.telegram.org/file/bot{self.token}/{path}"
        with requests.get(url,stream=True,timeout=120) as r:
            r.raise_for_status()
            with open(dest,"wb") as f:
                for chunk in r.iter_content(1024*1024):
                    if chunk: f.write(chunk)
        return dest

    def send_message(self,chat_id,text):
        # Telegram text max 4096 chars. Chunk conservatively.
        chunks=[text[i:i+3900] for i in range(0,len(text),3900)] or [""]
        out=[]
        for chunk in chunks:
            r=requests.post(f"{self.base}/sendMessage",json={"chat_id":chat_id,"text":chunk,"disable_web_page_preview":True},timeout=30)
            r.raise_for_status(); out.append(r.json())
        return out

    def _send_file(self,method,chat_id,path,field,caption=None):
        with open(path,"rb") as f:
            data={"chat_id":str(chat_id)}
            if caption: data["caption"]=caption[:1000]
            r=requests.post(f"{self.base}/{method}",data=data,files={field:(Path(path).name,f)},timeout=120)
            r.raise_for_status()
            return r.json()

    def send_document(self,chat_id,path,caption=None):
        return self._send_file("sendDocument",chat_id,path,"document",caption)

    def send_audio(self,chat_id,path,caption=None):
        return self._send_file("sendAudio",chat_id,path,"audio",caption)

    def send_photo(self,chat_id,path,caption=None):
        return self._send_file("sendPhoto",chat_id,path,"photo",caption)
