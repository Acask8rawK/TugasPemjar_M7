import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT   = 587          # Port SMTP dengan TLS (di atas TCP)
EMAIL_PENGIRIM = os.getenv('EMAIL_PENGIRIM')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

def kirim_email_notifikasi(email_tujuan, nama, nomor_antrian):
    """Mengirim email notifikasi ke pelanggan menggunakan SMTP/TCP"""
    try:
        # Membuat koneksi TCP ke server SMTP
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.ehlo()          # Identifikasi klien ke server SMTP
        server.starttls()      # Upgrade ke koneksi TLS
        server.login(EMAIL_PENGIRIM, EMAIL_PASSWORD)

        msg = MIMEMultipart()
        msg['From']    = EMAIL_PENGIRIM
        msg['To']      = email_tujuan
        msg['Subject'] = f'[WashQueue] Giliran Anda Tiba! Nomor Antrian {nomor_antrian}'

        body = f'''
Halo {nama},

Giliran Anda telah tiba!
Nomor Antrian : {nomor_antrian}
Status        : Dipanggil

Silahkan segera menuju area cuci kendaraan.
Terima kasih telah menggunakan layanan WashQueue.
        '''
        msg.attach(MIMEText(body, 'plain'))

        server.sendmail(EMAIL_PENGIRIM, email_tujuan, msg.as_string())
        server.quit()  # Menutup koneksi TCP SMTP
        print(f'[SMTP/TCP] Email terkirim ke {email_tujuan}')
    except Exception as e:
        print(f'[SMTP/TCP] Gagal mengirim email: {e}')
