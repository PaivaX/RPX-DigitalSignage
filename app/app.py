import os
import queue
import shutil
import sqlite3
from collections import defaultdict
from flask import Flask, request, render_template, redirect, url_for, send_from_directory, jsonify, Response, stream_with_context, session
from werkzeug.utils import secure_filename

app = Flask(__name__)

# Configuração básica
app.secret_key = 'asda33443fff'
event_queues = defaultdict(queue.Queue)

def get_db():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    conn = sqlite3.connect(os.path.join(BASE_DIR, 'db', 'database.db'))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Cria as tabelas iniciais e insere config padrão se não existir."""
    conn = get_db()
    with conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            tv_id TEXT NOT NULL
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS plugins (
            tv_id TEXT PRIMARY KEY,
            show_clock INTEGER DEFAULT 1,
            show_weather INTEGER DEFAULT 1,
            custom_message TEXT DEFAULT '',
            timer INTEGER DEFAULT 5,
            transition TEXT DEFAULT 'fade-in',
            transition_time INTEGER DEFAULT 1,
            sound_enabled INTEGER DEFAULT 0,
            use_static_content INTEGER DEFAULT 0,
            company_name TEXT DEFAULT '',
            people_names TEXT DEFAULT '',
            logo_path TEXT DEFAULT '',
            imagem_lang TEXT DEFAULT 'PT'
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            nas_path TEXT,
            upload_path TEXT,
            admin_user TEXT,
            admin_password TEXT
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS static_library (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                tipo TEXT CHECK(tipo IN ('image', 'video')) NOT NULL,
                descricao TEXT DEFAULT ''
            )''')

        # Se não existe config, insere
        cfg = conn.execute('SELECT * FROM config WHERE id = 1').fetchone()
        if not cfg:
            conn.execute('''
                INSERT INTO config (id, nas_path, upload_path, admin_user, admin_password)
                VALUES (1, ?, ?, ?, ?)
            ''', (
                r'\\192.168.1.2\Multimedia\Material reunioes\Fundos de Ecra',
                'static/uploads',
                'admin',
                'password123'
            ))
    conn.close()

init_db()

def load_app_config():
    """Carrega as configs do BD (tabela config) e retorna como dict."""
    conn = get_db()
    cfg = conn.execute('SELECT * FROM config WHERE id = 1').fetchone()
    conn.close()
    return cfg

# Carrega config do BD e ajusta no Flask
config_data = load_app_config()
app.config['UPLOAD_FOLDER'] = config_data['upload_path']
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm','mov'}

NAS_PATH = config_data['nas_path']
user = config_data['admin_user']
password = config_data['admin_password']

DISPLAY_NAMES = {
    'TV1': 'TV-ENTRADA',
    'TV2': 'TV-SALAREUNIOES'
}

# Garante que as pastas existam
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('db', exist_ok=True)

# ------------------- MIDDLEWARE LOGIN -------------------
@app.before_request
def require_login():
    # Rotas que exigem login
    protected_routes = [
        'admin', 'upload_file', 'delete_image',
        'import_nas', 'config', 'update_plugins', 
        'update_timer'
    ]
    if request.endpoint in protected_routes and 'logged_in' not in session:
        return redirect(url_for('login'))

# ------------------- FUNÇÕES AUXILIARES -------------------
def allowed_file(filename):
    """Valida a extensão do ficheiro."""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in app.config['ALLOWED_EXTENSIONS']

# ------------------- ROTAS DE LOGIN/LOGOUT ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == user and request.form['password'] == password:
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('login.html', error='Credenciais inválidas')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# ------------------- ROTA DE CONFIGURAÇÕES ----------------
@app.route('/config', methods=['GET', 'POST'])
def config():
    conn = get_db()
    if request.method == 'POST':
        nas_path = request.form['nas_path']
        upload_path = request.form['upload_path']
        admin_user = request.form['admin_user']
        admin_password = request.form['admin_password']

        with conn:
            conn.execute('''
                UPDATE config
                SET nas_path = ?, upload_path = ?, admin_user = ?, admin_password = ?
                WHERE id = 1
            ''', (nas_path, upload_path, admin_user, admin_password))

        # Actualiza variáveis globais
        global NAS_PATH, user, password
        NAS_PATH = nas_path
        app.config['UPLOAD_FOLDER'] = upload_path
        user = admin_user
        password = admin_password

        return redirect(url_for('config'))

    config_db = conn.execute('SELECT * FROM config WHERE id = 1').fetchone()
    static_items = conn.execute('SELECT * FROM static_library').fetchall()
    conn.close()
    return render_template('config.html', config=config_db, static_library=static_items, DISPLAY_NAMES=DISPLAY_NAMES)

# ------------------- ROTA SSE (EVENTSOURCE) ---------------
@app.route('/events/<tv_id>')
def sse_stream(tv_id):
    def event_stream():
        q = event_queues[tv_id]
        while True:
            try:
                # Espera no máximo 5 segundos antes de mandar um keep-alive
                event = q.get(timeout=5)
                yield f"data: {event}\n\n"
            except queue.Empty:
                # Keep-alive para manter a ligação aberta e o browser não "desligar"
                yield ":\n\n"
    return Response(stream_with_context(event_stream()), mimetype='text/event-stream')


# ------------------- ROTA PRINCIPAL (ADMIN) ----------------
@app.route('/')
def admin():
    conn = get_db()

    # Carrega imagens
    images = conn.execute('SELECT * FROM images').fetchall()

    # Carrega plugins (timer incluído)
    plugins = conn.execute('SELECT * FROM plugins').fetchall()
    plugins_dict = {p['tv_id']: dict(p) for p in plugins}

    # Carrega biblioteca estática
    static_library = conn.execute('SELECT * FROM static_library').fetchall()
    
    # Garante que cada TV tem um registo em plugins (com todos os campos novos)
    for tv in DISPLAY_NAMES.keys():
        if tv not in plugins_dict:
            plugins_dict[tv] = {
                'tv_id': tv,
                'show_clock': 1,
                'show_weather': 1,
                'custom_message': '',
                'transition': 'fade-in',
                'transition_time': 1,
                'sound_enabled': 0,
                'use_static_content': 0,
                'company_name': '',
                'people_names': '',
                'logo_path': '',
                'imagem_lang': 'PT',
                'timer': 5
            }
            conn.execute('''
                INSERT INTO plugins (
                    tv_id, show_clock, show_weather, custom_message, 
                    transition, transition_time, sound_enabled, 
                    use_static_content, company_name, people_names, 
                    logo_path, imagem_lang, timer
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (tv, 1, 1, '', 'fade-in', 1, 0, 0, '', '', '', 'PT', 5))
            conn.commit()

    # Listar ficheiros da NAS
    nas_files = []
    if os.path.exists(NAS_PATH):
        nas_files = [f for f in os.listdir(NAS_PATH) if allowed_file(f)]

    conn.close()

    return render_template(
        'admin.html',
        images=images,
        plugins=plugins_dict,
        DISPLAY_NAMES=DISPLAY_NAMES,
        nas_files=nas_files,
        static_library=static_library
    )
    
@app.route('/delete_library_item/<int:item_id>', methods=['POST'])
def delete_library_item(item_id):
    conn = get_db()
    item = conn.execute('SELECT filename FROM static_library WHERE id = ?', (item_id,)).fetchone()
    
    if item:
        # Remove ficheiro físico
        file_path = os.path.join('static', 'library', item['filename'])
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"[✔] Removido da biblioteca: {file_path}")

        # Remove da BD
        conn.execute('DELETE FROM static_library WHERE id = ?', (item_id,))
        conn.commit()
    
    conn.close()
    return redirect(url_for('admin', msg='Conteúdo removido da biblioteca.', type='warning'))


# ------------------- IMPORTAR DA NAS ----------------
@app.route('/import_nas', methods=['POST'])
def import_nas():
    filename = request.form['filename']
    tv_id = request.form['tv_id']

    if not tv_id or tv_id not in DISPLAY_NAMES:
        return redirect(url_for('admin'))

    nas_origem = os.path.join(NAS_PATH, filename)
    tv_folder = os.path.join(app.config['UPLOAD_FOLDER'], tv_id)
    os.makedirs(tv_folder, exist_ok=True)
    destino = os.path.join(tv_folder, filename)

    if os.path.exists(nas_origem):
        try:
            with open(nas_origem, 'rb') as src, open(destino, 'wb') as dst:
                dst.write(src.read())

            conn = get_db()
            with conn:
                conn.execute('''
                    INSERT INTO images (filename, tv_id)
                    VALUES (?, ?)
                ''', (f"{tv_id}/{filename}", tv_id))

            print(f"[✔] Importado da NAS: {filename} -> TV {tv_id}")

            # Notifica a TV via SSE
            event_queues[tv_id].put('reload')

        except Exception as e:
            print('[✘] Erro ao importar da NAS:', e)
    else:
        print('[✘] Ficheiro não encontrado na NAS:', nas_origem)

    return redirect(url_for('admin', msg='Imagem importada da NAS!', type='success'))

# ------------------- UPLOAD DE FICHEIROS ----------------
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files or 'tv_id' not in request.form:
        return redirect(url_for('admin'))

    file = request.files['file']
    tv_id = request.form['tv_id']

    if not tv_id or tv_id not in DISPLAY_NAMES.keys():
        return redirect(url_for('admin'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        tv_folder = os.path.join(app.config['UPLOAD_FOLDER'], tv_id)
        os.makedirs(tv_folder, exist_ok=True)

        file_path = os.path.join(tv_folder, filename)
        
        try:
            file.save(file_path)
            conn = get_db()
            with conn:
                conn.execute('INSERT INTO images (filename, tv_id) VALUES (?, ?)', (f"{tv_id}/{filename}", tv_id))
            print(f"[✔] Upload: {filename} -> TV {tv_id}")

            # Notifica SSE
            event_queues[tv_id].put('reload')

        except Exception as e:
            print(f"[✘] Erro ao guardar o ficheiro: {e}")
    else:
        print("[✘] Ficheiro inválido ou extensão não permitida.")

    return redirect(url_for('admin'))

@app.route('/get_timer/<tv_id>')
def get_timer(tv_id):
    conn = get_db()
    setting = conn.execute('SELECT timer FROM plugins WHERE tv_id = ?', (tv_id,)).fetchone()
    conn.close()
    return jsonify({'timer': setting['timer'] if setting else 5})

@app.route('/reset_timers', methods=['POST'])
def reset_timers():
    conn = get_db()
    with conn:
        conn.execute('DELETE FROM settings')
    return redirect(url_for('admin'))

@app.route('/add_static_to_tv', methods=['POST'])
def add_static_to_tv():
    file_id = request.form['file_id']
    tv_id = request.form['tv_id']

    conn = get_db()
    item = conn.execute('SELECT * FROM static_library WHERE id = ?', (file_id,)).fetchone()

    if item:
        src_path = os.path.join('static/library', item['filename'])
        tv_folder = os.path.join(app.config['UPLOAD_FOLDER'], tv_id)
        os.makedirs(tv_folder, exist_ok=True)
        dest_path = os.path.join(tv_folder, item['filename'])

        if os.path.exists(src_path):
            shutil.copyfile(src_path, dest_path)
            conn.execute('INSERT INTO images (filename, tv_id) VALUES (?, ?)', (f"{tv_id}/{item['filename']}", tv_id))
            conn.commit()
            event_queues[tv_id].put('reload')

    conn.close()
    return redirect(url_for('admin', msg='Conteúdo adicionado à TV!', type='success'))

@app.route('/upload_static_library', methods=['POST'])
def upload_static_library():
    file = request.files['file']
    tipo = request.form['tipo']

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        library_path = os.path.join('static', 'library')
        os.makedirs(library_path, exist_ok=True)
        file_path = os.path.join(library_path, filename)
        file.save(file_path)

        conn = get_db()
        with conn:
            conn.execute('INSERT INTO static_library (filename, tipo) VALUES (?, ?)', (filename, tipo))

        conn.close()
        return redirect(url_for('admin', msg='Ficheiro adicionado à biblioteca!', type='success'))
    else:
        return redirect(url_for('admin', msg='Ficheiro inválido ou extensão não permitida.', type='warning'))


# ------------------- PLAYER E PLAYLIST ----------------
@app.route('/player/<tv_id>')
def player(tv_id):
    return render_template('player.html', tv_id=tv_id)

@app.route('/playlist/<tv_id>')
def playlist(tv_id):
    conn = get_db()
    rows = conn.execute('SELECT * FROM images WHERE tv_id = ?', (tv_id,)).fetchall()
    plugin = conn.execute('SELECT use_static_content FROM plugins WHERE tv_id = ?', (tv_id,)).fetchone()
    conn.close()

    data = []

    # Adiciona conteúdos da TV normalmente
    for img in rows:
        filename = img['filename']
        ext = filename.rsplit('.', 1)[-1].lower()
        tipo = 'image' if ext in ['png', 'jpg', 'jpeg', 'gif'] else 'video'
        data.append({'filename': filename, 'type': tipo})

    # Se ativado, adiciona defaults
    if plugin and plugin['use_static_content']:
        static_dir = os.path.join('static', 'defaults')
        for file in os.listdir(static_dir):
            ext = file.rsplit('.', 1)[-1].lower()
            tipo = 'image' if ext in ['png', 'jpg', 'jpeg', 'gif'] else 'video'
            data.append({'filename': f'defaults/{file}', 'type': tipo})

    return jsonify(data)


@app.route('/update_tv_config', methods=['POST'])
def update_tv_config():
    tv_id = request.form['tv_id']
    timer = int(request.form['timer'])
    transition = request.form['transition']
    transition_time = float(request.form['transition_time'])
    show_clock = 1 if request.form.get('show_clock') else 0
    show_weather = 1 if request.form.get('show_weather') else 0
    custom_message = request.form.get('custom_message', '')
    sound_enabled = 1 if request.form.get('sound_enabled') else 0
    company_name = request.form.get('company_name', '')
    people_names = request.form.get('people_names', '')
    imagem_lang = request.form.get('imagem_lang', 'PT')
    remove_logo = request.form.get('remove_logo')

    print(f"[DEBUG] Dados recebidos - TV: {tv_id}, Lang: {imagem_lang}")

    conn = get_db()

    # Pega logo atual
    plugin = conn.execute('SELECT logo_path FROM plugins WHERE tv_id = ?', (tv_id,)).fetchone()
    existing_logo = plugin['logo_path'] if plugin else ''
    print(f"[DEBUG] Logo atual no BD: {existing_logo}")

    # Processa logo novo
    logo_file = request.files.get('logo')
    logo_path = ''
    if logo_file and allowed_file(logo_file.filename):
        filename = secure_filename(logo_file.filename)
        tv_folder = os.path.join(app.config['UPLOAD_FOLDER'], tv_id)
        os.makedirs(tv_folder, exist_ok=True)
        file_path = os.path.join(tv_folder, filename)
        logo_file.save(file_path)
        logo_path = f"{tv_id}/{filename}"
        print(f"[✔] Novo logo guardado: {logo_path}")

    # Lógica de remoção
    final_logo = existing_logo
    if remove_logo:
        if existing_logo:
            logo_path_disk = os.path.join(app.config['UPLOAD_FOLDER'], existing_logo)
            if os.path.exists(logo_path_disk):
                os.remove(logo_path_disk)
                print(f"[✔] Logo removido do disco: {logo_path_disk}")
            final_logo = ''
    elif logo_path:
        final_logo = logo_path  # Novo logo substitui o anterior

    try:
        with conn:
            conn.execute('''
                INSERT INTO plugins (
                    tv_id, show_clock, show_weather, custom_message, 
                    transition, transition_time, sound_enabled, 
                    company_name, people_names, logo_path, imagem_lang, timer
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tv_id) DO UPDATE SET
                    show_clock = excluded.show_clock,
                    show_weather = excluded.show_weather,
                    custom_message = excluded.custom_message,
                    transition = excluded.transition,
                    transition_time = excluded.transition_time,
                    sound_enabled = excluded.sound_enabled,
                    company_name = excluded.company_name,
                    people_names = excluded.people_names,
                    logo_path = excluded.logo_path,
                    imagem_lang = excluded.imagem_lang,
                    timer = excluded.timer
            ''', (tv_id, show_clock, show_weather, custom_message, transition, transition_time, sound_enabled, company_name, people_names, final_logo, imagem_lang, timer))

        print("[✔] Configurações atualizadas no BD")
        event_queues[tv_id].put('reload')

    except Exception as e:
        print(f"[✘] Erro ao atualizar: {e}")

    finally:
        conn.close()

    return redirect(url_for('admin', msg='Configurações atualizadas!', type='success'))



@app.route('/get_fallback/<tv_id>')
def get_fallback(tv_id):
    conn = get_db()
    plugin = conn.execute('SELECT * FROM plugins WHERE tv_id = ?', (tv_id,)).fetchone()
    conn.close()

    return jsonify({
        'company_name': plugin['company_name'],
        'people_names': plugin['people_names'],
        'logo': f"/static/uploads/{plugin['logo_path']}" if plugin['logo_path'] else ''
    })

@app.route('/get_imagem_lang/<tv_id>')
def get_imagem_lang(tv_id):
    conn = get_db()
    plugin = conn.execute('SELECT imagem_lang FROM plugins WHERE tv_id = ?', (tv_id,)).fetchone()
    conn.close()
    return jsonify({'lang': plugin['imagem_lang'] if plugin else 'PT'})


# ------------------- ROTA PARA SERVIR FICHEIROS (opcional) ----------------
@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    """Serve ficheiros de /static/uploads, incluindo subpastas."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ------------------- DELETE ----------------
@app.route('/delete/<int:image_id>', methods=['POST'])
def delete_image(image_id):
    conn = get_db()
    row = conn.execute('SELECT * FROM images WHERE id = ?', (image_id,)).fetchone()
    if row:
        tv_id = row['tv_id']
        # Remove do BD
        conn.execute('DELETE FROM images WHERE id = ?', (image_id,))
        conn.commit()

        # Remove ficheiro físico
        path_file = os.path.join(app.config['UPLOAD_FOLDER'], row['filename'])
        if os.path.exists(path_file):
            os.remove(path_file)
            print(f"[✔] Removido ficheiro {path_file}")

        # Notifica SSE
        event_queues[tv_id].put('reload')
    conn.close()
    return redirect(url_for('admin', msg='Imagem removida com sucesso!', type='warning'))


# ------------------- TOGGLE SOUND ----------------
@app.route('/toggle_sound/<tv_id>', methods=['POST'])
def toggle_sound(tv_id):
    conn = get_db()
    plugin = conn.execute('SELECT sound_enabled FROM plugins WHERE tv_id = ?', (tv_id,)).fetchone()
    if not plugin:
        return jsonify({'error': 'TV não encontrada'}), 404

    novo_valor = 0 if plugin['sound_enabled'] else 1
    conn.execute('UPDATE plugins SET sound_enabled=? WHERE tv_id=?', (novo_valor, tv_id))
    conn.commit()
    conn.close()

    event_queues[tv_id].put('reload')
    return jsonify({'sound_enabled': novo_valor})

# ------------------- API PLUGINS ----------------
@app.route('/get_plugins/<tv_id>')
def get_plugins(tv_id):
    conn = get_db()
    plugin = conn.execute('SELECT * FROM plugins WHERE tv_id = ?', (tv_id,)).fetchone()
    conn.close()
    return jsonify(dict(plugin) if plugin else {})

# ------------------- MAIN ----------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)