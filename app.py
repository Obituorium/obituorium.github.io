from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)
download_folder = os.path.expanduser("~/Downloads")
cookies_file = None

def get_default_download_folder():
    return os.path.expanduser("~/Downloads")

download_folder = get_default_download_folder()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/fetch_metadata', methods=['POST'])
def fetch_metadata():
    global cookies_file
    if not request.json or 'url' not in request.json:
        return jsonify({'error': 'Missing URL in request'}), 400

    video_url = request.json['url']
    try:
        ydl_opts = {'quiet': True}
        if cookies_file:
            ydl_opts['cookiefile'] = cookies_file

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)

        return jsonify({
            'title': info.get('title'),
            'thumbnail': info['thumbnails'][0]['url'],
            'duration': info.get('duration')
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/fetch_playlist', methods=['POST'])
def fetch_playlist():
    global cookies_file
    if not request.json or 'url' not in request.json:
        return jsonify({'error': 'Missing URL in request'}), 400

    original_url = request.json['url']
    parsed = urlparse(original_url)
    query = parse_qs(parsed.query)
    playlist_id = query.get('list', [None])[0]

    if not playlist_id:
        return jsonify({'error': 'No playlist ID found in URL'}), 400

    playlist_url = f'https://www.youtube.com/playlist?list={playlist_id}'

    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': False,
            'dump_single_json': True,
            'playlistend': 100
        }
        if cookies_file:
            ydl_opts['cookiefile'] = cookies_file

        entries = []
        skipped = 0

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(playlist_url, download=False)

            for entry in playlist_info.get('entries', []):
                try:
                    if not entry.get('thumbnails') or not entry.get('webpage_url'):
                        entry = ydl.extract_info(entry['url'], download=False)

                    entries.append({
                        'title': entry.get('title', 'Untitled'),
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry['thumbnails'][0]['url'] if entry.get('thumbnails') else '',
                        'url': entry.get('webpage_url', '')
                    })
                except Exception:
                    skipped += 1

        return jsonify({'entries': entries, 'skipped': skipped})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download_video():
    global cookies_file
    if not request.json or 'url' not in request.json:
        return jsonify({'error': 'Missing URL in request'}), 400

    video_url = request.json['url']
    quality = request.json.get('quality', 'best')
    resolution = request.json.get('resolution', None)

    ydl_opts = {
        'quiet': False,
        'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
        'format': quality
    }

    if resolution:
        ydl_opts['format'] = f"bestvideo[height<={resolution}]+bestaudio/best"
    if cookies_file:
        ydl_opts['cookiefile'] = cookies_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            video_filename = ydl.prepare_filename(info)

        return jsonify({'success': True, 'message': 'Download ready', 'download_link': f'/get_download/{os.path.basename(video_filename)}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_download/<filename>')
def get_download(filename):
    file_path = os.path.join(download_folder, filename)
    return send_file(file_path, as_attachment=True)

@app.route('/set_cookies', methods=['POST'])
def set_cookies():
    global cookies_file
    file = request.files.get('file')

    if not file:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    cookies_path = os.path.join(download_folder, 'cookies.txt')
    file.save(cookies_path)
    cookies_file = cookies_path

    return jsonify({'success': True, 'message': 'Cookies file uploaded successfully'})

if __name__ == '__main__':
    app.run(debug=True)
