"""Main routes for Absolute Story Manager."""
from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Redirect to dashboard."""
    return render_template('dashboard.html')


@main_bp.route('/dashboard')
def dashboard():
    """Dashboard page - story cockpit."""
    return render_template('dashboard.html')


@main_bp.route('/chapters')
def chapters():
    """Chapter list and management."""
    return render_template('chapters/list.html')


@main_bp.route('/chapters/<chapter_id>')
def chapter_detail(chapter_id):
    """Chapter detail view."""
    return render_template('chapters/detail.html', chapter_id=chapter_id)


@main_bp.route('/characters')
def characters():
    """Character list and management."""
    return render_template('characters/list.html')


@main_bp.route('/characters/<character_id>')
def character_detail(character_id):
    """Character detail view."""
    return render_template('characters/detail.html', character_id=character_id)


@main_bp.route('/kanban')
def kanban():
    """Kanban board for story planning."""
    return render_template('plans/kanban.html')


@main_bp.route('/timeline')
def timeline():
    """Timeline view for story events."""
    return render_template('plans/timeline.html')


@main_bp.route('/outline')
def outline():
    """Nested outline view."""
    return render_template('plans/outline.html')


@main_bp.route('/world')
def world():
    """World building library."""
    return render_template('world/index.html')


@main_bp.route('/world/<entry_id>')
def world_entry(entry_id):
    """World entry detail."""
    return render_template('world/detail.html', entry_id=entry_id)


@main_bp.route('/export')
def export():
    """Export page."""
    return render_template('export.html')


@main_bp.route('/search')
def search():
    """Full-text search page."""
    return render_template('search.html')


@main_bp.route('/settings')
def settings():
    """Settings page."""
    return render_template('settings.html')
