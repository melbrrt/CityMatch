from flask import Flask
from flask_cors import CORS
from routes.main_routes import bp as main_bp
import os

app = Flask(__name__)
CORS(app)

# Enregistrer le blueprint
app.register_blueprint(main_bp)

if __name__ == "__main__":
    # Affichage pour debug
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(BASE_DIR, "data", "csv_fusionne.csv")
    print("Serveur OK ➜ http://127.0.0.1:5000")
    print("Chemin CSV:", csv_path)
    print("CSV existe ?", os.path.exists(csv_path))
    
    app.run(debug=True, port=5000)
