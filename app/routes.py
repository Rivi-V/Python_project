from flask import render_template, flash, redirect, url_for, request
from app import app, db
from app.forms import LoginForm, RegistrationForm, EditProfileForm
from flask_login import current_user, login_user, logout_user, login_required
import sqlalchemy as sa
from app.models import User, Product, Orders
from datetime import datetime, timezone, date, timedelta 

from calendar import monthcalendar
from datetime import datetime

def generate_calendar(year, month, booked_ranges):
    cal = monthcalendar(year, month)
    today = datetime.now().date()
    
    # Преобразуем календарь в список дат
    calendar_dates = []
    for week in cal:
        week_dates = []
        for day in week:
            if day == 0:
                week_dates.append(0)
            else:
                date_str = f"{year}-{month:02d}-{day:02d}"
                week_dates.append(date_str)
        calendar_dates.append(week_dates)
    
    return calendar_dates

@app.route('/')
@app.route('/index')
@login_required
def index():
  return render_template("index.html", title='Home Page')

@app.route('/login', methods=['GET', 'POST'])
def login():
  if current_user.is_authenticated:
    return redirect(url_for('index'))
  form = LoginForm()
  if form.validate_on_submit():
    user = db.session.scalar(
      sa.select(User).where(User.username == form.username.data))
    if user is None or not user.check_password(form.password.data):
      flash('Invalid username or password')
      return redirect(url_for('login'))
    login_user(user, remember=form.remember_me.data)
    return redirect(url_for('index'))
  return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/user/<username>')
@login_required
def user(username):
    user = db.first_or_404(sa.select(User).where(User.username == username))
    return render_template('user.html', user=user)


@app.route('/product/<int:id>')
@login_required
def product(id):
    product = db.first_or_404(sa.select(Product).where(Product.id == id))
    
    # Получаем занятые даты
    booked_dates = db.session.execute(
        sa.select(Orders.c.start_date, Orders.c.end_date)
        .where(Orders.c.product_id == id)
        .where(Orders.c.status == 'active')
    ).fetchall()
    
    # Создаем список всех занятых дней
    booked_days = []
    for start, end in booked_dates:
        current = start
        while current <= end:
            booked_days.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
    
    # Генерируем календарь на текущий месяц
    today = date.today()
    cal = monthcalendar(today.year, today.month)
    
    # Форматируем календарь для шаблона
    calendar = []
    for week in cal:
        week_days = []
        for day in week:
            if day == 0:
                week_days.append(0)
            else:
                date_str = f"{today.year}-{today.month:02d}-{day:02d}"
                week_days.append(date_str)
        calendar.append(week_days)
    
    return render_template('product.html', 
                         product=product,
                         calendar=calendar,
                         booked_days=booked_days,
                         today=today.strftime('%Y-%m-%d'))

@app.route('/product/<int:product_id>/book', methods=['POST'])
@login_required
def book_product(product_id):
    try:
        # Конвертируем строки в даты
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        location = request.form['location']
        
        # Проверяем, что конечная дата не раньше начальной
        if end_date < start_date:
            flash('Конечная дата не может быть раньше начальной', 'error')
            return redirect(url_for('product', id=product_id))
            
        # Проверяем доступность дат
        conflict = db.session.execute(
            sa.select(Orders)
            .where(Orders.c.product_id == product_id)
            .where(Orders.c.status == 'active')
            .where(
                ((Orders.c.start_date <= end_date) & (Orders.c.end_date >= start_date))
            )
        ).first()
        
        if conflict:
            flash('Выбранные даты уже заняты', 'error')
            return redirect(url_for('product', id=product_id))
        
        # Создаем бронь
        db.session.execute(
            Orders.insert().values(
                user_id=current_user.id,
                product_id=product_id,
                start_date=start_date,  # Теперь это date объект
                end_date=end_date,      # Теперь это date объект
                location=location,
                status='active'
            )
        )
        db.session.commit()
        
        flash('Товар успешно забронирован!', 'success')
        return redirect(url_for('product', id=product_id))
        
    except ValueError:
        flash('Неверный формат даты', 'error')
        return redirect(url_for('product', id=product_id))

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.now(timezone.utc)
        db.session.commit()

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash('Your changes have been saved.')
        return redirect(url_for('edit_profile'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title='Edit Profile',
                           form=form)