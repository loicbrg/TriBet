"""Point d'entrée simple pour lancer TriBet sur Raspberry Pi."""
import os
from app import app, db

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    host = os.environ.get('HOST', '0.0.0.0')
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'

    print(f"🏊 TriBet démarré sur http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
