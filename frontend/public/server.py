from flask import Flask, send_from_directory
import os

app = Flask(__name__, static_folder='.')

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    if path != "" and os.path.exists(path):
        return send_from_directory(os.path.dirname(path), os.path.basename(path))
    else:
        return send_from_directory(app.static_folder, 'index.html')

if __name__ == '__main__':
    app.run(port=5175, host='0.0.0.0')