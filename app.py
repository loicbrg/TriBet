from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime
from models import db, User, Event, Market, Selection, Bet
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tribet-embrunman-2026-secret')
_db_path = os.environ.get('TRIBET_DB', os.path.join(os.path.dirname(__file__), 'tribet.db'))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{_db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

MOIS_FR = ['', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
           'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
JOURS_FR = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']

@app.template_filter('date_fr')
def date_fr(dt, fmt='long'):
    """Formate une date en français."""
    if fmt == 'long':
        return f"{JOURS_FR[dt.weekday()]} {dt.day} {MOIS_FR[dt.month]} {dt.year}"
    if fmt == 'court':
        return f"{dt.day:02d}/{dt.month:02d}/{dt.year}"
    if fmt == 'heure':
        return f"{JOURS_FR[dt.weekday()]} {dt.day} {MOIS_FR[dt.month]} {dt.year} à {dt.strftime('%Hh%M')}"
    return str(dt)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Connectez-vous pour accéder à cette page.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ── Helpers ────────────────────────────────────────────────────────────────────

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def recalculate_odds(market):
    """
    Recalcule les cotes de toutes les sélections d'un marché ouvert
    en fonction du volume de mises (style pari-mutuel avec lissage).
    Les cotes évoluent : plus on mise sur X, plus la cote de X baisse
    et celles des autres montent.
    """
    if market.status != 'open':
        return {}

    selections = market.selections
    if not selections:
        return {}

    # Volume misé par sélection
    amounts = {sel.id: sel.total_staked for sel in selections}
    total = sum(amounts.values())

    # En dessous de 10 € de mises totales : cotes fixes (pas assez de signal)
    if total < 10:
        return {sel.id: sel.odds for sel in selections}

    n = len(selections)
    # Lissage pour éviter les cotes extrêmes quand une sélection n'a pas de mises
    # Chaque sélection reçoit un « pseudo-montant » basé sur ses cotes initiales
    smoothing = {}
    total_inv_base = sum(1.0 / sel.base_odds for sel in selections)
    for sel in selections:
        # Proportionnel à l'inverse de la cote initiale (proxy du poids attendu)
        smoothing[sel.id] = (total * 0.3) * (1.0 / sel.base_odds) / total_inv_base

    updated = {}
    total_effective = total + sum(smoothing.values())
    for sel in selections:
        effective = amounts[sel.id] + smoothing[sel.id]
        # Cote "juste" sans marge : total / mise_on_sel
        raw_odds = total_effective / effective
        # On applique une légère marge (5 %) — cosmétique sur de la monnaie fictive
        new_odds = round(max(1.05, min(100.0, raw_odds * 0.95)), 2)
        if sel.odds != new_odds:
            sel.odds = new_odds
        updated[sel.id] = new_odds

    return updated


# ── Public routes ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    upcoming = Event.query.filter(Event.status.in_(['upcoming', 'live'])).order_by(Event.race_date).all()
    finished = Event.query.filter_by(status='finished').order_by(Event.race_date.desc()).limit(3).all()
    top_users = User.query.order_by(User.balance.desc()).limit(5).all()
    return render_template('index.html', upcoming=upcoming, finished=finished, top_users=top_users)


@app.route('/events')
def events():
    status_filter = request.args.get('status', 'all')
    if status_filter == 'all':
        all_events = Event.query.order_by(Event.race_date.desc()).all()
    else:
        all_events = Event.query.filter_by(status=status_filter).order_by(Event.race_date.desc()).all()
    return render_template('betting/events.html', events=all_events, status_filter=status_filter)


@app.route('/events/<int:event_id>')
def event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    user_bets = {}
    if current_user.is_authenticated:
        for market in event.markets:
            for sel in market.selections:
                bets = Bet.query.filter_by(user_id=current_user.id, selection_id=sel.id).all()
                if bets:
                    user_bets[sel.id] = bets
    return render_template('betting/event.html', event=event, user_bets=user_bets)


@app.route('/participants')
def participants():
    # Récupère tous les noms uniques de sélections dans des marchés "participant"
    PARTICIPANT_TYPES = ('winner', 'winner_swim', 'winner_bike', 'winner_run', 'duel')
    sels = (Selection.query
            .join(Market).join(Event)
            .filter(Market.market_type.in_(PARTICIPANT_TYPES))
            .filter(Event.status.in_(['upcoming', 'live', 'finished']))
            .all())
    # Déduplique par nom, conserve drapeau et accumule les mises
    seen = {}
    for s in sels:
        if s.name not in seen:
            seen[s.name] = {'flag': s.flag, 'total_staked': 0, 'markets': 0}
        seen[s.name]['total_staked'] += s.total_staked
        seen[s.name]['markets'] += 1
    participants_list = [{'name': n, **v} for n, v in seen.items()]
    participants_list.sort(key=lambda p: p['name'])
    return render_template('betting/participants.html', participants=participants_list)


@app.route('/participants/<path:name>')
def participant_detail(name):
    PARTICIPANT_TYPES = ('winner', 'winner_swim', 'winner_bike', 'winner_run', 'duel')
    selections = (Selection.query
                  .join(Market).join(Event)
                  .filter(Selection.name == name)
                  .filter(Market.market_type.in_(PARTICIPANT_TYPES))
                  .order_by(Event.race_date, Market.id)
                  .all())
    if not selections:
        abort(404)
    user_bets = {}
    if current_user.is_authenticated:
        for sel in selections:
            bets = Bet.query.filter_by(user_id=current_user.id, selection_id=sel.id).all()
            if bets:
                user_bets[sel.id] = bets
    flag = selections[0].flag if selections else '🇫🇷'
    return render_template('betting/participant.html',
                           participant_name=name, flag=flag,
                           selections=selections, user_bets=user_bets)


@app.route('/leaderboard')
def leaderboard():
    users = User.query.filter_by(is_admin=False).order_by(User.balance.desc()).all()
    return render_template('betting/leaderboard.html', users=users)


@app.route('/my-bets')
@login_required
def my_bets():
    status_filter = request.args.get('status', 'all')
    query = Bet.query.filter_by(user_id=current_user.id)
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    bets = query.order_by(Bet.created_at.desc()).all()
    return render_template('betting/my_bets.html', bets=bets, status_filter=status_filter)


# ── Betting API ────────────────────────────────────────────────────────────────

@app.route('/api/bet', methods=['POST'])
@login_required
def place_bet():
    data = request.get_json()
    selection_id = data.get('selection_id')
    amount = data.get('amount')

    if not selection_id or not amount:
        return jsonify({'success': False, 'message': 'Données manquantes'}), 400

    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Montant invalide'}), 400

    if amount < 1:
        return jsonify({'success': False, 'message': 'Mise minimum : 1 pt'}), 400

    if amount > 10000:
        return jsonify({'success': False, 'message': 'Mise maximum : 10 000 pts'}), 400

    selection = Selection.query.get(selection_id)
    if not selection:
        return jsonify({'success': False, 'message': 'Sélection introuvable'}), 404

    if selection.market.status != 'open':
        return jsonify({'success': False, 'message': 'Ce marché est fermé'}), 400

    if selection.market.event.status == 'finished':
        return jsonify({'success': False, 'message': 'Cet événement est terminé'}), 400

    if current_user.balance < amount:
        return jsonify({'success': False, 'message': 'Solde insuffisant'}), 400

    odds_at_bet = selection.odds  # Cote verrouillée au moment du pari
    potential_win = round(amount * odds_at_bet, 2)
    bet = Bet(
        user_id=current_user.id,
        selection_id=selection_id,
        amount=amount,
        potential_win=potential_win,
        status='pending'
    )
    current_user.balance = round(current_user.balance - amount, 2)
    db.session.add(bet)
    db.session.flush()  # Persiste le bet avant recalcul

    # Recalculer les cotes du marché avec le nouveau pari inclus
    updated_odds = recalculate_odds(selection.market)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Pari placé ! Gain potentiel : {int(potential_win)} pts',
        'new_balance': current_user.balance,
        'potential_win': potential_win,
        'updated_odds': updated_odds,  # Frontend peut mettre à jour les boutons
    })


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter(
            (User.email == identifier) | (User.username == identifier)
        ).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash(f'Bienvenue, {user.username} !', 'success')
            return redirect(next_page or url_for('index'))
        flash('Identifiant ou mot de passe incorrect.', 'danger')
    return render_template('auth/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        errors = []
        if len(username) < 3:
            errors.append("Le pseudo doit faire au moins 3 caractères.")
        if len(password) < 6:
            errors.append("Le mot de passe doit faire au moins 6 caractères.")
        if password != confirm:
            errors.append("Les mots de passe ne correspondent pas.")
        if User.query.filter_by(username=username).first():
            errors.append("Ce pseudo est déjà pris.")
        if User.query.filter_by(email=email).first():
            errors.append("Cet e-mail est déjà utilisé.")

        if errors:
            for e in errors:
                flash(e, 'danger')
        else:
            user = User(username=username, email=email, balance=500.0)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash(f'Compte créé ! Vous démarrez avec 500 points. Bonne chance !', 'success')
            return redirect(url_for('index'))
    return render_template('auth/register.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Vous êtes déconnecté.', 'info')
    return redirect(url_for('index'))


# ── Admin ──────────────────────────────────────────────────────────────────────

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    events = Event.query.order_by(Event.race_date.desc()).all()
    users_count = User.query.count()
    bets_count = Bet.query.count()
    pending_bets = Bet.query.filter_by(status='pending').count()
    return render_template('admin/dashboard.html',
                           events=events,
                           users_count=users_count,
                           bets_count=bets_count,
                           pending_bets=pending_bets)


@app.route('/admin/events/new', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_new_event():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        race_date_str = request.form.get('race_date', '')
        status = request.form.get('status', 'upcoming')

        try:
            race_date = datetime.strptime(race_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash('Format de date invalide.', 'danger')
            return render_template('admin/event_form.html', event=None)

        event = Event(name=name, description=description, location=location,
                      race_date=race_date, status=status)
        db.session.add(event)
        db.session.commit()
        flash('Événement créé.', 'success')
        return redirect(url_for('admin_event_detail', event_id=event.id))
    return render_template('admin/event_form.html', event=None)


@app.route('/admin/events/<int:event_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_event_detail(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'update_status':
            event.status = request.form.get('status', event.status)
            db.session.commit()
            flash('Statut mis à jour.', 'success')
        elif action == 'add_market':
            market_name = request.form.get('market_name', '').strip()
            market_desc = request.form.get('market_desc', '').strip()
            if market_name:
                market = Market(event_id=event.id, name=market_name, description=market_desc)
                db.session.add(market)
                db.session.commit()
                flash('Marché ajouté.', 'success')
        return redirect(url_for('admin_event_detail', event_id=event_id))
    return render_template('admin/event_detail.html', event=event)


@app.route('/admin/markets/<int:market_id>/add-selection', methods=['POST'])
@login_required
@admin_required
def admin_add_selection(market_id):
    market = Market.query.get_or_404(market_id)
    name = request.form.get('name', '').strip()
    flag = request.form.get('flag', '').strip()
    description = request.form.get('description', '').strip()
    try:
        odds = float(request.form.get('odds', '2.0'))
    except ValueError:
        flash('Cote invalide.', 'danger')
        return redirect(url_for('admin_event_detail', event_id=market.event_id))

    if name and odds > 1.0:
        sel = Selection(market_id=market_id, name=name, flag=flag,
                        description=description, odds=odds, base_odds=odds)
        db.session.add(sel)
        db.session.commit()
        flash(f'Sélection "{name}" ajoutée.', 'success')
    else:
        flash('Nom et cote (>1.0) requis.', 'danger')
    return redirect(url_for('admin_event_detail', event_id=market.event_id))


@app.route('/admin/markets/<int:market_id>/resolve', methods=['POST'])
@login_required
@admin_required
def admin_resolve_market(market_id):
    market = Market.query.get_or_404(market_id)
    winner_id = request.form.get('winner_id', type=int)

    if not winner_id:
        flash('Sélectionnez un vainqueur.', 'danger')
        return redirect(url_for('admin_event_detail', event_id=market.event_id))

    winner = Selection.query.get(winner_id)
    if not winner or winner.market_id != market_id:
        flash('Sélection invalide.', 'danger')
        return redirect(url_for('admin_event_detail', event_id=market.event_id))

    now = datetime.utcnow()
    for sel in market.selections:
        sel.is_winner = (sel.id == winner_id)
        for bet in sel.bets:
            if bet.status == 'pending':
                if sel.is_winner:
                    bet.status = 'won'
                    bet.user.balance = round(bet.user.balance + bet.potential_win, 2)
                else:
                    bet.status = 'lost'
                bet.resolved_at = now

    market.status = 'resolved'
    db.session.commit()
    flash(f'Marché résolu. Vainqueur : {winner.name}', 'success')
    return redirect(url_for('admin_event_detail', event_id=market.event_id))


@app.route('/admin/markets/<int:market_id>/toggle', methods=['POST'])
@login_required
@admin_required
def admin_toggle_market(market_id):
    market = Market.query.get_or_404(market_id)
    if market.status == 'open':
        market.status = 'suspended'
        flash('Marché suspendu.', 'warning')
    elif market.status == 'suspended':
        market.status = 'open'
        flash('Marché rouvert.', 'success')
    db.session.commit()
    return redirect(url_for('admin_event_detail', event_id=market.event_id))


@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@app.route('/admin/users/<int:user_id>/adjust', methods=['POST'])
@login_required
@admin_required
def admin_adjust_balance(user_id):
    user = User.query.get_or_404(user_id)
    try:
        amount = float(request.form.get('amount', 0))
    except ValueError:
        flash('Montant invalide.', 'danger')
        return redirect(url_for('admin_users'))
    user.balance = round(max(0, user.balance + amount), 2)
    db.session.commit()
    flash(f'Solde de {user.username} ajusté à {int(user.balance)} pts.', 'success')
    return redirect(url_for('admin_users'))


# ── Admin — Gestion des paris ──────────────────────────────────────────────────

@app.route('/admin/bets')
@login_required
@admin_required
def admin_bets():
    status_filter = request.args.get('status', 'all')
    user_filter   = request.args.get('user_id', type=int)
    event_filter  = request.args.get('event_id', type=int)

    query = Bet.query.join(Selection).join(Market).join(Event)
    if status_filter != 'all':
        query = query.filter(Bet.status == status_filter)
    if user_filter:
        query = query.filter(Bet.user_id == user_filter)
    if event_filter:
        query = query.filter(Market.event_id == event_filter)

    bets  = query.order_by(Bet.created_at.desc()).all()
    users  = User.query.order_by(User.username).all()
    events = Event.query.order_by(Event.race_date.desc()).all()
    return render_template('admin/bets.html',
                           bets=bets, users=users, events=events,
                           status_filter=status_filter,
                           user_filter=user_filter,
                           event_filter=event_filter)


@app.route('/admin/bets/add', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_add_bet():
    users      = User.query.filter_by(is_admin=False).order_by(User.username).all()
    events     = Event.query.order_by(Event.race_date.desc()).all()
    selections = Selection.query.join(Market).filter(Market.status == 'open').order_by(Market.name, Selection.name).all()

    if request.method == 'POST':
        user_id      = request.form.get('user_id', type=int)
        selection_id = request.form.get('selection_id', type=int)
        try:
            amount = float(request.form.get('amount', 0))
        except ValueError:
            flash('Montant invalide.', 'danger')
            return render_template('admin/add_bet.html', users=users, events=events, selections=selections)

        user      = User.query.get(user_id)
        selection = Selection.query.get(selection_id)

        if not user or not selection:
            flash('Utilisateur ou sélection introuvable.', 'danger')
            return render_template('admin/add_bet.html', users=users, events=events, selections=selections)

        if amount <= 0:
            flash('Le montant doit être positif.', 'danger')
            return render_template('admin/add_bet.html', users=users, events=events, selections=selections)

        deduct = request.form.get('deduct_balance') == 'on'
        if deduct and user.balance < amount:
            flash(f'Solde insuffisant pour {user.username} ({int(user.balance)} pts).', 'danger')
            return render_template('admin/add_bet.html', users=users, events=events, selections=selections)

        potential_win = round(amount * selection.odds, 2)
        bet = Bet(user_id=user.id, selection_id=selection.id,
                  amount=amount, potential_win=potential_win, status='pending')
        if deduct:
            user.balance = round(user.balance - amount, 2)
        db.session.add(bet)
        db.session.flush()
        recalculate_odds(selection.market)
        db.session.commit()
        flash(f'Pari ajouté : {user.username} → {selection.name} ({int(amount)} pts).', 'success')
        return redirect(url_for('admin_bets'))

    return render_template('admin/add_bet.html', users=users, events=events, selections=selections)


@app.route('/admin/bets/<int:bet_id>/cancel', methods=['POST'])
@login_required
@admin_required
def admin_cancel_bet(bet_id):
    bet = Bet.query.get_or_404(bet_id)
    if bet.status != 'pending':
        flash('Seuls les paris en attente peuvent être annulés.', 'warning')
        return redirect(url_for('admin_bets'))

    refund = request.form.get('refund') == 'on'
    bet.status = 'cancelled'
    if refund:
        bet.user.balance = round(bet.user.balance + bet.amount, 2)
        flash(f'Pari annulé et {int(bet.amount)} pts remboursés à {bet.user.username}.', 'success')
    else:
        flash(f'Pari annulé (sans remboursement).', 'warning')
    db.session.commit()
    return redirect(url_for('admin_bets'))


@app.route('/admin/bets/<int:bet_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_bet(bet_id):
    bet = Bet.query.get_or_404(bet_id)
    if request.method == 'POST':
        try:
            new_amount = float(request.form.get('amount', bet.amount))
        except ValueError:
            flash('Montant invalide.', 'danger')
            return render_template('admin/edit_bet.html', bet=bet)

        new_status = request.form.get('status', bet.status)
        if new_status not in ('pending', 'won', 'lost', 'cancelled'):
            flash('Statut invalide.', 'danger')
            return render_template('admin/edit_bet.html', bet=bet)

        # Ajuste le solde si le montant change
        delta = new_amount - bet.amount
        if delta != 0:
            bet.user.balance = round(max(0, bet.user.balance - delta), 2)
        bet.amount = new_amount
        bet.potential_win = round(new_amount * bet.selection.odds, 2)

        # Crédit automatique si passage à "won"
        if new_status == 'won' and bet.status != 'won':
            bet.user.balance = round(bet.user.balance + bet.potential_win, 2)
        # Débit si retour de "won" à autre chose
        elif bet.status == 'won' and new_status != 'won':
            bet.user.balance = round(max(0, bet.user.balance - bet.potential_win), 2)

        bet.status = new_status
        db.session.commit()
        flash('Pari modifié.', 'success')
        return redirect(url_for('admin_bets'))
    return render_template('admin/edit_bet.html', bet=bet)


@app.route('/admin/bets/<int:bet_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_bet(bet_id):
    bet = Bet.query.get_or_404(bet_id)
    if bet.status == 'pending':
        refund = request.form.get('refund') == 'on'
        if refund:
            bet.user.balance = round(bet.user.balance + bet.amount, 2)
    db.session.delete(bet)
    db.session.commit()
    flash('Pari supprimé définitivement.', 'danger')
    return redirect(url_for('admin_bets'))


@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=False)
