from flask import Blueprint, render_template

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@main_bp.route('/stories')
def stories():
    return render_template('stories.html')

@main_bp.route('/story/<int:story_id>')
def story_detail(story_id):
    return render_template('story_detail.html', story_id=story_id)

@main_bp.route('/characters')
def characters():
    return render_template('characters.html')

@main_bp.route('/kanban')
def kanban():
    return render_template('kanban.html')

@main_bp.route('/timeline')
def timeline():
    return render_template('timeline.html')

@main_bp.route('/worldbuilding')
def worldbuilding():
    return render_template('worldbuilding.html')

@main_bp.route('/export')
def export():
    return render_template('export.html')

@main_bp.route('/settings')
def settings():
    return render_template('settings.html')
