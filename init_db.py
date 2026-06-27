"""
Script d'initialisation de la base de données TriBet.
Paris entre amis sur le Triathlon L d'Embrun 2026 — dimanche 28 juin 2026, 7h30.
Usage : python init_db.py
"""
from app import app
from models import db, User, Event, Market, Selection
from datetime import datetime

# ── Participants ─────────────────────────────────────────────────────────────
# Format : (nom, emoji drapeau, cote de base)
# Cotes proches car tous amis → se recalculent dynamiquement selon les mises

PARTICIPANTS = [
    ("Bergery Loïc",       "🇫🇷", 4.00),
    ("Blanc-Gras Bastien", "🇫🇷", 4.00),
    ("Blanc-Gras Clément", "🇫🇷", 4.00),
    ("Crespin Lucas",      "🇫🇷", 4.00),
    ("Blanc-Gras Bernard", "🇫🇷", 4.00),
    ("Ghio Florian",       "🇫🇷", 4.00),
    ("Ghio Eric",          "🇫🇷", 4.00),
    ("Montabord Joffrey",  "🇫🇷", 4.00),
]

# Cotes spécifiques pour le marché "Vainqueur de la course"
# (plus affinées, basées sur le niveau supposé de chacun)
WINNER_ODDS = [
    ("Bergery Loïc",       "🇫🇷", 1.80),
    ("Blanc-Gras Bastien", "🇫🇷", 10.00),
    ("Blanc-Gras Clément", "🇫🇷", 3.50),
    ("Crespin Lucas",      "🇫🇷", 2.00),
    ("Blanc-Gras Bernard", "🇫🇷", 10.00),
    ("Ghio Florian",       "🇫🇷", 1.60),
    ("Ghio Eric",          "🇫🇷", 10.00),
    ("Montabord Joffrey",  "🇫🇷", 10.00),
]

# Plages de temps pour les marchés discipline
NATATION_TRANCHES = [
    ("Sous 1h00",       "", 4.00),
    ("1h00 – 1h15",     "", 2.00),
    ("1h15 – 1h30",     "", 2.50),
    ("Plus de 1h30",    "", 4.50),
]

VELO_TRANCHES = [
    ("Sous 5h30",       "", 5.00),
    ("5h30 – 6h00",     "", 2.20),
    ("6h00 – 6h45",     "", 1.80),
    ("6h45 – 7h30",     "", 2.50),
    ("Plus de 7h30",    "", 5.00),
]

CAP_TRANCHES = [
    ("Sous 3h15",       "", 5.50),
    ("3h15 – 3h45",     "", 2.00),
    ("3h45 – 4h15",     "", 1.80),
    ("4h15 – 5h00",     "", 2.50),
    ("Plus de 5h00",    "", 4.00),
]

TOTAL_TRANCHES = [
    ("Sous 10h30",      "", 6.00),
    ("10h30 – 11h30",   "", 2.50),
    ("11h30 – 12h30",   "", 1.90),
    ("12h30 – 14h00",   "", 2.00),
    ("Plus de 14h00",   "", 3.00),
]

ABANDON_TRANCHES = [
    ("0 abandon dans notre groupe",       "", 2.50),
    ("1 abandon dans notre groupe",       "", 2.00),
    ("2 abandons dans notre groupe",      "", 3.00),
    ("3 abandons ou + dans notre groupe", "", 5.00),
]

# ── Marchés spéciaux ─────────────────────────────────────────────────────────

PODIUM_G3 = [  # Top 3 général toutes catégories confondues dans notre groupe
    ("Bergery Loïc termine top 3 du groupe",      "🇫🇷", 4.00),
    ("Blanc-Gras Bastien termine top 3 du groupe","🇫🇷", 4.00),
    ("Blanc-Gras Clément termine top 3 du groupe","🇫🇷", 4.00),
    ("Crespin Lucas termine top 3 du groupe",     "🇫🇷", 4.00),
    ("Blanc-Gras Bernard termine top 3 du groupe","🇫🇷", 4.00),
    ("Ghio Florian termine top 3 du groupe",      "🇫🇷", 4.00),
    ("Ghio Eric termine top 3 du groupe",         "🇫🇷", 4.00),
    ("Montabord Joffrey termine top 3 du groupe", "🇫🇷", 4.00),
]

PREMIER_BLANC_GRAS = [
    ("Blanc-Gras Bastien", "🇫🇷", 4.00),
    ("Blanc-Gras Clément", "🇫🇷", 4.00),
    ("Blanc-Gras Bernard", "🇫🇷", 4.00),
]

PREMIER_GHIO = [
    ("Ghio Florian", "🇫🇷", 4.00),
    ("Ghio Eric",    "🇫🇷", 4.00),
]

FINIR_SOUS_12H = [
    (name, flag, 4.00) for name, flag, _ in [
        ("Bergery Loïc",       "🇫🇷", 0),
        ("Blanc-Gras Bastien", "🇫🇷", 0),
        ("Blanc-Gras Clément", "🇫🇷", 0),
        ("Crespin Lucas",      "🇫🇷", 0),
        ("Blanc-Gras Bernard", "🇫🇷", 0),
        ("Ghio Florian",       "🇫🇷", 0),
        ("Ghio Eric",          "🇫🇷", 0),
        ("Montabord Joffrey",  "🇫🇷", 0),
    ]
]

PREMIER_NATATION_ABSOLU = [  # Meilleur temps natation (pas classement général)
    (name, flag, 4.00) for name, flag, _ in [
        ("Bergery Loïc",       "🇫🇷", 0),
        ("Blanc-Gras Bastien", "🇫🇷", 0),
        ("Blanc-Gras Clément", "🇫🇷", 0),
        ("Crespin Lucas",      "🇫🇷", 0),
        ("Blanc-Gras Bernard", "🇫🇷", 0),
        ("Ghio Florian",       "🇫🇷", 0),
        ("Ghio Eric",          "🇫🇷", 0),
        ("Montabord Joffrey",  "🇫🇷", 0),
    ]
]


def add_market(event_id, name, description, market_type, selections):
    m = Market(event_id=event_id, name=name, description=description,
               market_type=market_type, status='open')
    db.session.add(m)
    db.session.flush()
    for name_s, flag, odds in selections:
        db.session.add(Selection(market_id=m.id, name=name_s, flag=flag,
                                 odds=odds, base_odds=odds))
    return m


def create_event():
    event = Event(
        name="Triathlon L d'Embrun 2026",
        description=(
            "Le Triathlon L d'Embrun — 3,8 km natation dans le lac de Serre-Ponçon, "
            "188 km vélo avec les cols de Vars et d'Izoard, 42,2 km course à pied. "
            "Pariez sur lequel de nos amis terminera en tête !"
        ),
        location="Embrun, Hautes-Alpes, France",
        race_date=datetime(2026, 6, 28, 7, 30, 0),
        status='upcoming',
    )
    db.session.add(event)
    db.session.flush()

    # 1. Premier du groupe (classement général entre nous) — cotes affinées
    add_market(event.id,
        "Premier du groupe — classement général",
        "Lequel de nos 8 participants terminera avec le meilleur classement général ?",
        'winner', WINNER_ODDS)

    # 2. Meilleur temps natation
    add_market(event.id,
        "Meilleure natation du groupe",
        "Qui réalisera le meilleur temps de natation parmi nous ? (3,8 km)",
        'winner_swim', PARTICIPANTS)

    # 3. Meilleur temps vélo
    add_market(event.id,
        "Meilleur vélo du groupe",
        "Qui réalisera le meilleur temps de vélo parmi nous ? (188 km, Vars + Izoard)",
        'winner_bike', PARTICIPANTS)

    # 4. Meilleure course à pied
    add_market(event.id,
        "Meilleure course à pied du groupe",
        "Qui réalisera le meilleur marathon parmi nous ? (42,2 km)",
        'winner_run', PARTICIPANTS)

    # 5. Temps total du meilleur (tranche)
    add_market(event.id,
        "Temps total du premier du groupe",
        "Dans quelle tranche de temps terminera le meilleur d'entre nous ?",
        'total_time', TOTAL_TRANCHES)

    # 6. Temps natation du meilleur (tranche)
    add_market(event.id,
        "Temps natation du meilleur du groupe",
        "Dans quelle tranche tombera le meilleur temps de natation du groupe ?",
        'split_swim', NATATION_TRANCHES)

    # 7. Temps vélo du meilleur (tranche)
    add_market(event.id,
        "Temps vélo du meilleur du groupe",
        "Dans quelle tranche tombera le meilleur temps de vélo du groupe ?",
        'split_bike', VELO_TRANCHES)

    # 8. Temps course à pied du meilleur (tranche)
    add_market(event.id,
        "Temps course à pied du meilleur du groupe",
        "Dans quelle tranche tombera le meilleur temps de CAP du groupe ?",
        'split_run', CAP_TRANCHES)

    # 9. Nombre d'abandons
    add_market(event.id,
        "Combien d'abandons dans notre groupe ?",
        "Combien de nos 5 participants ne franchiront pas la ligne d'arrivée ?",
        'special', ABANDON_TRANCHES)

    # 10. Duels directs
    add_market(event.id,
        "Duel : Ghio Florian vs Ghio Eric",
        "Qui finira le mieux classé entre Florian et Eric Ghio ?",
        'duel',
        [("Ghio Florian", "🇫🇷", 4.00),
         ("Ghio Eric",    "🇫🇷", 4.00)])

    add_market(event.id,
        "Duel : Crespin Lucas vs Montabord Joffrey",
        "Qui finira le mieux classé entre Lucas et Joffrey ?",
        'duel',
        [("Crespin Lucas",     "🇫🇷", 4.00),
         ("Montabord Joffrey", "🇫🇷", 4.00)])

    add_market(event.id,
        "Duel : Bergery Loïc vs Blanc-Gras Bastien",
        "Qui finira le mieux classé entre Loïc et Bastien ?",
        'duel',
        [("Bergery Loïc",       "🇫🇷", 4.00),
         ("Blanc-Gras Bastien", "🇫🇷", 4.00)])

    add_market(event.id,
        "Duel : Blanc-Gras Clément vs Blanc-Gras Bernard",
        "Qui finira le mieux classé entre Clément et Bernard Blanc-Gras ?",
        'duel',
        [("Blanc-Gras Clément", "🇫🇷", 4.00),
         ("Blanc-Gras Bernard", "🇫🇷", 4.00)])

    # 14. Premier de la famille Blanc-Gras
    add_market(event.id,
        "Premier de la famille Blanc-Gras",
        "Qui des Blanc-Gras (Bastien, Clément, Bernard) terminera le mieux classé ?",
        'duel', PREMIER_BLANC_GRAS)

    # 15. Premier des Ghio
    add_market(event.id,
        "Premier de la famille Ghio",
        "Qui de Florian ou Eric Ghio terminera le mieux classé ?",
        'duel', PREMIER_GHIO)

    # 16. Qui finit sous 12h ?
    add_market(event.id,
        "Premier du groupe à finir sous 12h",
        "Pariez sur le premier participant de notre groupe dont le temps total sera sous 12h. "
        "Si personne ne passe sous les 12h, les paris sont remboursés.",
        'winner', FINIR_SOUS_12H)

    # 17. Meilleur nageur du groupe (pas rangé par classement général mais par split)
    add_market(event.id,
        "Meilleur nageur absolu du groupe",
        "Qui réalisera le meilleur temps de natation parmi nous 8 ?",
        'winner_swim', PREMIER_NATATION_ABSOLU)

    # 18. Temps de l'abandon (si au moins un)
    add_market(event.id,
        "Quel segment causera le plus d'abandons ?",
        "Si au moins un participant abandonne, sur quel segment cela se produira-t-il ?",
        'special',
        [("Natation (abandon avant la sortie de l'eau)", "", 6.00),
         ("Vélo (abandon sur le parcours vélo)", "",          2.00),
         ("Course à pied (abandon après T2)", "",             2.50),
         ("Personne n'abandonne", "",                         3.00)])

    # 19. Qui récupère le mieux ? (temps entre 1er et dernier finisher du groupe)
    add_market(event.id,
        "Écart entre le 1er et le dernier du groupe",
        "Quel sera l'écart de temps entre le premier et le dernier finisher de notre groupe ?",
        'special',
        [("Moins de 1h d'écart",        "", 5.00),
         ("1h – 2h d'écart",            "", 2.00),
         ("2h – 3h d'écart",            "", 2.50),
         ("Plus de 3h d'écart",         "", 3.50)])

    # 20. Le coup de cœur (pari surprise)
    add_market(event.id,
        "Pari surprise : qui sera le plus surprenant ?",
        "Quel participant surpassera le plus les attentes par rapport à son classement général dans le groupe ?",
        'winner', [(name, "🇫🇷", 4.00) for name, _, _ in
                   [("Bergery Loïc","",""),("Blanc-Gras Bastien","",""),
                    ("Blanc-Gras Clément","",""),("Crespin Lucas","",""),
                    ("Blanc-Gras Bernard","",""),("Ghio Florian","",""),
                    ("Ghio Eric","",""),("Montabord Joffrey","","")]])

    return event


def main():
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Compte admin
        admin = User(username='admin', email='admin@tribet.fr', balance=0.0, is_admin=True)
        admin.set_password('admin2025')
        db.session.add(admin)

        # Comptes parieurs (chacun peut créer le sien sur le site)
        demo = User(username='loic', email='loic@tribet.fr', balance=500.0)
        demo.set_password('demo1234')
        db.session.add(demo)

        event = create_event()
        db.session.commit()

        print("✅  Base de données initialisée !")
        print(f"    Événement : {event.name}")
        print(f"    Date      : Dimanche 28 juin 2026 à 7h30")
        print(f"    Marchés   : {len(event.markets)}")
        print()
        print(f"    Participants  : {len(PARTICIPANTS)}")
        for p in PARTICIPANTS:
            print(f"      • {p[0]}")
        print()
        print("    Compte admin : admin / admin2025")
        print("    Compte démo  : loic / demo1234")
        print()
        print("    Les cotes évoluent automatiquement à chaque mise !")


if __name__ == '__main__':
    main()
