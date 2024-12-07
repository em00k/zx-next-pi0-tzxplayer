from flask import Flask, jsonify, send_from_directory, send_file, request
import subprocess
import threading
import time
import os
import signal
import wave
from werkzeug.utils import secure_filename
import logging

app = Flask(__name__)

# Global variables to control playback
current_position = 0
is_playing = False
audio_thread = None
audio_path = "/var/www/docs/test.wav"
current_process = None
current_file = None

if not app.debug:
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)  # Only log warnings and errors

def convert_tzx_to_wav(tzx_path):
    try:
        # Get the filename without extension
        base_name = os.path.splitext(os.path.basename(tzx_path))[0]
        wav_path = f"/var/www/docs/{base_name}.wav"
        
        # Convert TZX to WAV using tape2wav
        cmd = f"tape2wav {tzx_path} {wav_path}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error converting TZX: {result.stderr}")
            return None
            
        # Convert to correct format using sox
        temp_wav = f"/var/www/docs/temp_{base_name}.wav"
        cmd = f"sox {wav_path} -r 44100 -c 2 -b 16 {temp_wav}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            os.replace(temp_wav, wav_path)
            return wav_path
        else:
            print(f"Error converting WAV format: {result.stderr}")
            return None
    except Exception as e:
        print(f"Error in conversion: {str(e)}")
        return None

def audio_player():
    global is_playing, current_position, current_process
    while True:
        if is_playing:
            try:
                if current_process is None:  # Only start a new process if none exists
                    print(f"Starting playback from position {current_position}")
                    skip_seconds = current_position
                    cmd = f"exec sox {audio_path} -t raw -b 16 -e signed-integer -r 44100 -c 2 - trim {skip_seconds} | exec aplay -f S16_LE -c 2 -r 44100"
                    current_process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
                
                if current_process and current_process.poll() is None:
                    current_position += 0.1
            except Exception as e:
                print(f"Error in audio_player: {str(e)}")
                is_playing = False
                current_process = None
            time.sleep(0.1)
        else:
            if current_process and current_process.poll() is None:
                os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
                current_process = None
            time.sleep(0.1)

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file part'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No selected file'})
    
    if file and file.filename.lower().endswith('.tzx'):
        try:
            # Save the uploaded TZX file
            filename = secure_filename(file.filename)
            tzx_path = os.path.join('/var/www/docs/', filename)
            file.save(tzx_path)
            
            # Convert TZX to WAV
            wav_path = convert_tzx_to_wav(tzx_path)
            
            if wav_path:
                # Clean up TZX file
                os.remove(tzx_path)
                return jsonify({
                    'success': True,
                    'status': 'complete',
                    'message': 'Conversion complete'
                })
            else:
                return jsonify({
                    'success': False, 
                    'status': 'error',
                    'error': 'Conversion failed'
                })
                
        except Exception as e:
            return jsonify({
                'success': False,
                'status': 'error',
                'error': str(e)
            })
    
    return jsonify({'success': False, 'error': 'Invalid file type'})

@app.route('/files')
def list_files():
    files = [f for f in os.listdir('/var/www/docs/') if f.endswith('.wav')]
    return jsonify(files)

@app.route('/play', methods=['POST'])
def play():
    global is_playing, audio_thread, current_process
    try:
        print("Play requested - Current state:", {
            "is_playing": is_playing,
            "has_process": current_process is not None,
            "has_thread": audio_thread is not None and audio_thread.is_alive()
        })
        
        is_playing = True
        if current_process:  # Clear any existing process
            os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
            current_process = None
            
        if audio_thread is None or not audio_thread.is_alive():
            audio_thread = threading.Thread(target=audio_player)
            audio_thread.daemon = True
            audio_thread.start()
            
        print("Play state after update:", {
            "is_playing": is_playing,
            "has_process": current_process is not None,
            "has_thread": audio_thread is not None and audio_thread.is_alive()
        })
        return jsonify({"status": "playing"})
    except Exception as e:
        print(f"Error in play endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/pause', methods=['POST'])
def pause():
    global is_playing
    is_playing = False
    return jsonify({"status": "paused"})

@app.route('/stop', methods=['POST'])
def stop():
    global is_playing, current_position, current_process
    try:
        print("Stop requested - Current state:", {
            "is_playing": is_playing,
            "position": current_position,
            "has_process": current_process is not None
        })
        
        is_playing = False
        current_position = 0
        if current_process:
            os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
            current_process = None
            subprocess.run("pkill -f aplay", shell=True)
            subprocess.run("pkill -f sox", shell=True)  # Also kill any sox processes
            
        print("Stop state after update:", {
            "is_playing": is_playing,
            "position": current_position,
            "has_process": current_process is not None
        })
        return jsonify({"status": "stopped"})
    except Exception as e:
        print(f"Error in stop endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    # Don't log status checks
    if request.headers.get('X-Status-Check'):
        return jsonify({
            "is_playing": is_playing,
            "position": current_position,
            "current_file": current_file
        })
    return jsonify({
        "is_playing": is_playing,
        "position": current_position,
        "current_file": current_file
    })

@app.route('/seek/<float:position>', methods=['POST'])
def seek(position):
    global current_position, current_process, is_playing
    current_position = position
    if current_process and current_process.poll() is None:
        current_process.terminate()
        current_process = None
    return jsonify({"status": "seeked", "position": position})

@app.route('/duration')
def get_duration():
    try:
        print(f"Getting duration for: {audio_path}")
        with wave.open(audio_path, 'rb') as wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            duration = frames / float(rate)
            print(f"Duration calculated: {duration} seconds")
            return jsonify({"duration": duration})
    except Exception as e:
        print(f"Error getting duration: {str(e)}")
        return jsonify({"duration": 0, "error": str(e)})

@app.route('/select/<filename>', methods=['POST'])
def select_file(filename):
    global audio_path, current_file
    try:
        # Construct the full path
        new_path = os.path.join('/var/www/docs/', filename)
        
        # Verify the file exists
        if not os.path.exists(new_path):
            return jsonify({'success': False, 'error': 'File not found'}), 404
            
        # Update the audio path and current file
        audio_path = new_path
        current_file = filename
        print(f"Selected audio file: {audio_path}")
        
        # Stop any current playback
        global is_playing, current_position, current_process
        is_playing = False
        current_position = 0
        if current_process:
            os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
            current_process = None
            
        return jsonify({
            'success': True,
            'file': filename,
            'path': audio_path
        })
        
    except Exception as e:
        print(f"Error selecting file: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    try:
        # Only allow deletion of WAV files for safety
        if not filename.endswith('.wav'):
            return jsonify({'success': False, 'error': 'Can only delete WAV files'}), 400
            
        file_path = os.path.join('/var/www/docs/', filename)
        if os.path.exists(file_path):
            # If this is the current file being played, stop playback
            global current_file, is_playing, current_process
            if current_file == filename:
                is_playing = False
                current_file = None
                if current_process:
                    os.killpg(os.getpgid(current_process.pid), signal.SIGTERM)
                    current_process = None
            
            os.remove(file_path)
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'File not found'}), 404
    except Exception as e:
        print(f"Error deleting file: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
