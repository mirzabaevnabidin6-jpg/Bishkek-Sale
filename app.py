import os, sqlite3, secrets
from datetime import date
from functools import wraps
from flask import Flask, render_template as flask_render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'local-demo-only-change-before-deployment'
DB = os.environ.get('DATABASE_PATH', os.path.join(os.path.dirname(__file__), 'sale.db'))
CATEGORIES = ['Футболка', 'Көйнөк', 'Шым', 'Жинсы', 'Куртка', 'Спорттук кийим', 'Бут кийим', 'Башка']
RU_CATEGORIES = ['Футболка', 'Рубашка', 'Брюки', 'Джинсы', 'Куртка', 'Спортивная одежда', 'Обувь', 'Другое']

def current_language():
    return session.get('lang', 'ky') if session.get('lang') in ('ky', 'ru') else 'ky'

def category_label(category):
    if current_language() == 'ru' and category in CATEGORIES:
        return RU_CATEGORIES[CATEGORIES.index(category)]
    return category

def render_template(template, **context):
    return flask_render_template(current_language() + '/' + template, lang=current_language(), category_label=category_label, **context)

@app.route('/language/<language>')
def set_language(language):
    if language not in ('ky', 'ru'):
        abort(404)
    session['lang'] = language
    destination = request.args.get('next', '/')
    if not destination.startswith('/') or destination.startswith('//'):
        destination = '/'
    return redirect(destination)


def localized(ky, ru):
    return ru if current_language() == 'ru' else ky

def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c

def init_db():
    with conn() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS shops (id INTEGER PRIMARY KEY, name TEXT NOT NULL, address TEXT NOT NULL, phone TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS promotions (id INTEGER PRIMARY KEY, shop_id INTEGER NOT NULL REFERENCES shops(id) ON DELETE CASCADE, title TEXT NOT NULL, category TEXT NOT NULL, original_price REAL NOT NULL, sale_price REAL NOT NULL, end_date TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', image_url TEXT NOT NULL DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP);''')
init_db()

def bootstrap_admin():
    email=os.environ.get('ADMIN_EMAIL','').strip().lower()
    password=os.environ.get('ADMIN_PASSWORD','')
    if email and len(password)>=8:
        with conn() as c:
            if not c.execute('SELECT id FROM admins LIMIT 1').fetchone():
                c.execute('INSERT INTO admins(email,password_hash) VALUES(?,?)',(email,generate_password_hash(password)))
                print('Admin created:',email)
bootstrap_admin()

@app.context_processor
def csrf_context():
    if 'csrf' not in session: session['csrf']=secrets.token_hex(24)
    return {'csrf_token':session['csrf']}

@app.before_request
def verify_csrf():
    if request.method=='POST' and not secrets.compare_digest(request.form.get('csrf_token',''),session.get('csrf','')):
        abort(400,description='Invalid form token. Refresh the page and try again.')

def admin_required(f):
    @wraps(f)
    def wrapped(*a,**kw):
        if not session.get('admin_id'): return redirect(url_for('admin_login'))
        return f(*a,**kw)
    return wrapped

def login_required(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if not session.get('shop_id'):
            flash(localized('Алгач аккаунтуңузга кириңиз.', 'Сначала войдите в аккаунт.'), 'warning')
            return redirect(url_for('login'))
        return f(*a, **kw)
    return wrapped

def read_promo_form():
    title = request.form.get('title','').strip()
    category = request.form.get('category','')
    description = request.form.get('description','').strip()[:1000]
    image_url = request.form.get('image_url','').strip()
    end_date = request.form.get('end_date','')
    try:
        original = float(request.form.get('original_price',''))
        sale = float(request.form.get('sale_price',''))
        deadline = date.fromisoformat(end_date)
    except ValueError:
        raise ValueError(localized('Баасы же датасы туура эмес.', 'Неверная цена или дата.'))
    if not title or len(title)>120 or category not in CATEGORIES or original<=0 or sale<0 or sale>=original or deadline<date.today():
        raise ValueError(localized('Талааларды текшериңиз: арзандатылган баа эски баадан төмөн, дата бүгүн же андан кийин болсун.', 'Проверьте поля: цена по акции должна быть ниже старой, дата — сегодня или позже.'))
    if image_url and not image_url.startswith(('https://','http://')):
        raise ValueError(localized('Сүрөткө http/https шилтемесин киргизиңиз.', 'Укажите ссылку http/https для изображения.'))
    return (title,category,original,sale,end_date,description,image_url)

@app.route('/')
def home():
    category = request.args.get('category','')
    q = request.args.get('q','').strip()
    sql = '''SELECT p.*,s.name AS shop_name,s.address,s.phone, ROUND((1-p.sale_price/p.original_price)*100) AS discount FROM promotions p JOIN shops s ON s.id=p.shop_id WHERE p.end_date>=?'''
    params=[date.today().isoformat()]
    if category in CATEGORIES:
        sql+=' AND p.category=?';params.append(category)
    if q:
        sql+=' AND (p.title LIKE ? OR s.name LIKE ? OR p.description LIKE ?)';params.extend(['%'+q+'%']*3)
    sql+=' ORDER BY p.created_at DESC, p.id DESC'
    with conn() as c:
        promos=c.execute(sql,params).fetchall()
        count=c.execute('SELECT COUNT(*) FROM shops').fetchone()[0]
    return render_template('home.html',promos=promos,categories=CATEGORIES,category=category,q=q,shop_count=count)

@app.route('/register')
def register():
    flash(localized('Дүкөндү администратор гана каттайт.', 'Магазины регистрирует только администратор.'),'warning')
    return redirect(url_for('login'))

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        with conn() as c:
            shop=c.execute('SELECT * FROM shops WHERE email=?',(request.form.get('email','').strip().lower(),)).fetchone()
        if shop and check_password_hash(shop['password_hash'],request.form.get('password','')):
            lang = current_language();session.clear();session['lang'] = lang;session['shop_id']=shop['id'];session['csrf']=secrets.token_hex(24)
            return redirect(url_for('dashboard'))
        flash(localized('Email же сырсөз туура эмес.', 'Неверный email или пароль.'),'error')
    return render_template('login.html')

@app.route('/logout',methods=['POST'])
def logout():
    lang = current_language();session.clear();session['lang'] = lang;return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    with conn() as c:
        shop=c.execute('SELECT * FROM shops WHERE id=?',(session['shop_id'],)).fetchone()
        promos=c.execute('SELECT * FROM promotions WHERE shop_id=? ORDER BY id DESC',(session['shop_id'],)).fetchall()
    if not shop: session.clear();return redirect(url_for('login'))
    return render_template('dashboard.html',shop=shop,promos=promos,today=date.today().isoformat())

@app.route('/promotion/new',methods=['GET','POST'])
@login_required
def new_promotion():
    if request.method=='POST':
        try:
            fields=read_promo_form()
            with conn() as c:
                c.execute('INSERT INTO promotions(shop_id,title,category,original_price,sale_price,end_date,description,image_url) VALUES(?,?,?,?,?,?,?,?)',(session['shop_id'],*fields))
            flash(localized('Акция кошулду!', 'Акция добавлена!'),'success');return redirect(url_for('dashboard'))
        except ValueError as e: flash(str(e),'error')
    return render_template('promotion_form.html',categories=CATEGORIES,promo=None,today=date.today().isoformat())

@app.route('/promotion/<int:pid>/edit',methods=['GET','POST'])
@login_required
def edit_promotion(pid):
    with conn() as c:
        promo=c.execute('SELECT * FROM promotions WHERE id=? AND shop_id=?',(pid,session['shop_id'])).fetchone()
    if not promo: abort(404)
    if request.method=='POST':
        try:
            fields=read_promo_form()
            with conn() as c:
                c.execute('UPDATE promotions SET title=?,category=?,original_price=?,sale_price=?,end_date=?,description=?,image_url=? WHERE id=? AND shop_id=?',(*fields,pid,session['shop_id']))
            flash(localized('Акция жаңыртылды.', 'Акция обновлена.'),'success');return redirect(url_for('dashboard'))
        except ValueError as e: flash(str(e),'error')
    return render_template('promotion_form.html',categories=CATEGORIES,promo=promo,today=date.today().isoformat())

@app.route('/promotion/<int:pid>/delete',methods=['POST'])
@login_required
def delete_promotion(pid):
    with conn() as c:
        c.execute('DELETE FROM promotions WHERE id=? AND shop_id=?',(pid,session['shop_id']))
    flash(localized('Акция өчүрүлдү.', 'Акция удалена.'),'success');return redirect(url_for('dashboard'))


@app.route('/admin/login',methods=['GET','POST'])
def admin_login():
    if request.method=='POST':
        with conn() as c:
            admin=c.execute('SELECT * FROM admins WHERE email=?',(request.form.get('email','').strip().lower(),)).fetchone()
        if admin and check_password_hash(admin['password_hash'],request.form.get('password','')):
            lang=current_language();session.clear();session.update(lang=lang,admin_id=admin['id'],csrf=secrets.token_hex(24))
            return redirect(url_for('admin_dashboard'))
        flash(localized('Кирүү маалыматы туура эмес.','Неверные данные для входа.'),'error')
    return render_template('admin_login.html')

@app.route('/admin')
@admin_required
def admin_dashboard():
    with conn() as c:
        shops=c.execute('SELECT s.*,COUNT(p.id) AS promo_count FROM shops s LEFT JOIN promotions p ON p.shop_id=s.id GROUP BY s.id ORDER BY s.id DESC').fetchall()
    return render_template('admin_dashboard.html',shops=shops)

@app.route('/admin/shops/new',methods=['GET','POST'])
@admin_required
def admin_new_shop():
    if request.method=='POST':
        name=request.form.get('name','').strip(); address=request.form.get('address','').strip();phone=request.form.get('phone','').strip();email=request.form.get('email','').strip().lower();password=request.form.get('password','')
        if not all((name,address,phone,email,password)) or '@' not in email or len(password)<8:
            flash(localized('Талааларды текшериңиз, сырсөз кеминде 8 белги.','Проверьте поля, пароль минимум 8 символов.'),'error')
        else:
            try:
                with conn() as c:
                    c.execute('INSERT INTO shops(name,address,phone,email,password_hash) VALUES(?,?,?,?,?)',(name,address,phone,email,generate_password_hash(password)))
                flash(localized('Дүкөн кошулду.','Магазин добавлен.'),'success')
                return redirect(url_for('admin_dashboard'))
            except sqlite3.IntegrityError:
                flash(localized('Email мурунтан бар.','Email уже используется.'),'error')
    return render_template('admin_shop_form.html',shop=None)

@app.route('/admin/shops/<int:sid>/edit',methods=['GET','POST'])
@admin_required
def admin_edit_shop(sid):
    with conn() as c: shop=c.execute('SELECT * FROM shops WHERE id=?',(sid,)).fetchone()
    if not shop: abort(404)
    if request.method=='POST':
        name=request.form.get('name','').strip();address=request.form.get('address','').strip();phone=request.form.get('phone','').strip();email=request.form.get('email','').strip().lower();password=request.form.get('password','')
        if not all((name,address,phone,email)) or '@' not in email or (password and len(password)<8):
            flash(localized('Маалымат туура эмес.','Некорректные данные.'),'error')
        else:
            try:
                with conn() as c:
                    if password:
                        c.execute('UPDATE shops SET name=?,address=?,phone=?,email=?,password_hash=? WHERE id=?',(name,address,phone,email,generate_password_hash(password),sid))
                    else:
                        c.execute('UPDATE shops SET name=?,address=?,phone=?,email=? WHERE id=?',(name,address,phone,email,sid))
                flash(localized('Дүкөн жаңыртылды.','Магазин обновлён.'),'success')
                return redirect(url_for('admin_dashboard'))
            except sqlite3.IntegrityError: flash(localized('Email мурунтан бар.','Email уже используется.'),'error')
    return render_template('admin_shop_form.html',shop=shop)

@app.route('/admin/shops/<int:sid>/delete',methods=['POST'])
@admin_required
def admin_delete_shop(sid):
    with conn() as c: c.execute('DELETE FROM shops WHERE id=?',(sid,))
    flash(localized('Дүкөн жана анын акциялары өчүрүлдү.','Магазин и его акции удалены.'),'success')
    return redirect(url_for('admin_dashboard'))

if __name__=='__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
