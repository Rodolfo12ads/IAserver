import subprocess

processes = [
    subprocess.Popen(["python", "server.py"]),
    subprocess.Popen(["python", "goldai_server.py"]),
    subprocess.Popen(["python", "auto_news_updater.py"])
]

for p in processes:
    p.wait()
