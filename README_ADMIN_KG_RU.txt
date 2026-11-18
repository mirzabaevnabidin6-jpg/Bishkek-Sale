BISHKEK SALE — Admin + Shop owners (KY/RU)

Linux иштетүү:
1) Архивди ачып, папкага кириңиз.
2) python3 -m venv .venv
3) source .venv/bin/activate
4) pip install -r requirements.txt
5) export ADMIN_EMAIL='admin@example.com'
6) export ADMIN_PASSWORD='CHANGE_ME_STRONG_123'
7) export SECRET_KEY='CHANGE_ME_RANDOM_SECRET_123456789'
8) python3 app.py
9) http://127.0.0.1:5000/admin/login — администратор
10) http://127.0.0.1:5000/login — дүкөн ээси

Администратор биринчи ишке киргизүүдө ADMIN_EMAIL жана ADMIN_PASSWORD аркылуу бир жолу түзүлөт. Кийинки ишке киргизүүлөрдө админдин логини/сырсөзү базада сакталат.
Администратор дүкөндү каттайт, дүкөн үчүн email/сырсөз берет, дүкөндү оңдойт же өчүрөт.
Дүкөн ээси өз акцияларын кошот, оңдойт жана өчүрөт.

МУРУНКУ БАЗАНЫ САКТОО: эски папкадагы sale.db файлын жаңы папкага көчүрүңүз (жаңы программа биринчи жолу иштетилгенге чейин). Дүкөндөр жана акциялар сакталат. Коопсуздук үчүн алдын ала резерв көчүрмө жасаңыз.
Бул жергиликтүү окуу версиясы. Интернетке чыгарууда HTTPS, күчтүү SECRET_KEY, база backup, админ аккаунтту коргоо, CSRF жана production server конфигурациясын текшериңиз.
