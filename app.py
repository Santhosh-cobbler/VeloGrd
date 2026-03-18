'''Backend For VeloGrd'''
# Dependencies
from flask import Flask, jsonify, session, render_template, request, redirect, url_for
import os
from dotenv import load_dotenv
from supabase import create_client, Client
import uuid
from werkzeug.utils import secure_filename


#OCR MODEL
from OCR.extraction import extract_the_data
#loading .env file
load_dotenv()
app = Flask(__name__)

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp"}
#make the folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


#register the key into the app
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')

#secretkey --> need to change it in whle deploying
app.secret_key = 'SECRETKEY'

#trigger supabase connectivity
supabase: Client = create_client(
    SUPABASE_URL, SUPABASE_KEY
)

print(f'''
URL {SUPABASE_URL},
KEY {SUPABASE_KEY}
''')


#landing_page
@app.route('/')
def landing_page():
    return render_template('landing_page.html')


#login-file
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        pwd = request.form.get('password')

        print(email,pwd)


        try:
            #login to the website using the email and password 
            data = supabase.auth.sign_in_with_password({
                'email':email,
                'password':pwd

            })
            '''storing the session data for each user so we can use this across the web'''
            # supabase session --> to check about the data of the user
            session['supabase_session'] = data.session.access_token
            #flask session
            session['user_id'] = data.user.id

            # if data of the user is in database it redirects to dashboard
            return redirect(url_for('dashboard'))

        except Exception as e:
            return f"Login Failed {e}"
            
    return render_template('login.html')


@app.route('/register',methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name= request.form.get('name')
        email = request.form.get('email')
        pwd = request.form.get('password')
        
        try:
            # add the user data like email and password to supabase
            response = supabase.auth.sign_up({
                'email': email,
                'password': pwd,
                'options':{
                    'data':{
                        'name':name
                    }
                }
            })


            return redirect(url_for('login'))

        except Exception as e:
            return f" Login failed {e}"

    return render_template('register.html')

'''
    read the instructions.txt
'''

#dashboard-> webpagee
@app.route('/dashboard')
def dashboard():
    token = session.get('supabase_session')
    try:
        if 'user_id' not in session:
            return redirect(url_for('login'))

        user_name  = 'GUEST'
        user_email = 'Log in'

        user_data = supabase.auth.get_user(token)
        if user_data:
            user_name  = user_data.user.user_metadata.get('name', 'Guest')
            user_email = user_data.user.email

        supabase.postgrest.auth(token)

        # ── All records for this user ──────────────────────────────
        all_res = supabase.table('ocr_records') \
            .select('*') \
            .eq('u_id', session['user_id']) \
            .execute()
        records = all_res.data or []

        total_records = len(records)

        # ── Latest record (last item inserted) ────────────────────
        latest_id      = None
        latest_address = None
        if records:
            last = records[-1]
            latest_id      = last.get('id')
            latest_address = last.get('Address')

        # ── No timestamp column → today_count = total (session-based) ──
        # We store how many existed at login and compare, OR just show total.
        # Using session to track: jobs done since this session started.
        if 'session_start_count' not in session:
            session['session_start_count'] = total_records
        today_count = total_records - session['session_start_count']

        # ── Shift utilization ─────────────────────────────────────
        shift_target = 20
        shift_pct    = min(round((today_count / shift_target) * 100), 100)

        # ── Plan distribution ─────────────────────────────────────
        plan_100 = sum(1 for r in records if '100' in str(r.get('Tariff plan', '')))
        plan_30  = sum(1 for r in records if '30'  in str(r.get('Tariff plan', '')))
        plan_total   = plan_100 + plan_30 or 1
        plan_100_pct = round((plan_100 / plan_total) * 100)
        plan_30_pct  = 100 - plan_100_pct

        # ── Weekly chart: split last 7 records into 7 buckets ─────
        # Since no timestamp, we divide all records into 7 equal day-buckets
        # to still render a meaningful bar chart shape
        chunk = max(len(records) // 7, 1)
        weekly_counts = []
        for i in range(7):
            start = i * chunk
            end   = start + chunk if i < 6 else len(records)
            weekly_counts.append(len(records[start:end]))

        # ── Recent 5 records for activity table ───────────────────
        recent = records[-5:][::-1]   # last 5, newest first

    except Exception as e:
        return f"Something went wrong: {e}"

    return render_template('dashboard.html',
        user_name      = user_name,
        user_email     = user_email,
        total_records  = total_records,
        today_count    = today_count,
        latest_id      = latest_id,
        latest_address = latest_address,
        shift_pct      = shift_pct,
        weekly_counts  = weekly_counts,
        plan_100_pct   = plan_100_pct,
        plan_30_pct    = plan_30_pct,
        recent         = recent,
    )

#upload the image
@app.route('/upload', methods=['GET','POST'])
def upload():
    if request.method == 'POST':
        client_name = request.form.get('client_name')
        images = request.files.getlist('images')

        # combined data --> there are 2 images to put data together
        combined_data ={}

        print('name--> ',client_name)
        for image in images:
            print(image.filename)

            filename = str(uuid.uuid4()) + "_" + secure_filename(image.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            print(file_path)
    
            image.save(file_path)
            ocr = extract_the_data(file_path)
            print(ocr)
            combined_data.update(ocr)
            print('Updated successfully')

        response = supabase.table('ocr_records').insert({
            'Name': client_name,
            'u_id': session['user_id'],
            'id': combined_data.get('id'),
            'status': combined_data.get('Status'),
            'Address': combined_data.get('Address'),
            'DSLID': combined_data.get('DSLID'),
            'Type':combined_data.get('Type'),
            'TEL': combined_data.get('TEL'),
            'Tariff_plan': combined_data.get('TariffPlan'),
            'date': combined_data.get('Date')
            
        }).execute()

    return render_template('upload.html')

@app.route('/view')
def view_data():
    token = session.get('supabase_session')
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    supabase.postgrest.auth(token)

    response = supabase.table('ocr_records').select('*').eq('u_id',session['user_id']).execute()
    infos = response.data
    
    return render_template('view.html',
        records=infos,
        total=len(infos),
        user_name=session.get('user_name'),
        user_email=session.get('user_email')
    )

@app.route('/raise_issue', methods=['GET', 'POST'])
def issue_raise():
    token = session.get('supabase_session')
    user_data = supabase.auth.get_user(token)
    
    if user_data:
        user_email = user_data.user.email

    if request.method == 'POST':
        issue = request.form.get('issue')
        try:
            response = supabase.table("issues").insert({
                'u_id': session['user_id'],
                'user_email': user_email,
                'user_name': 'Danny',
                'description': issue,
            }).execute()

        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return render_template('issue_raise.html')

if __name__ == '__main__':
    app.run(debug=True)
