import socket
import threading
from flask import Flask, render_template, request, redirect, url_for
from tcp_email_notif import kirim_email_notifikasi

app = Flask(__name__)

# Menyimpan data antrian di memori (list)
antrian = []
nomor_counter = 1

UDP_IP   = '255.255.255.255'  # Alamat broadcast LAN
UDP_PORT = 5005

def broadcast_udp(pesan):
    """Fungsi untuk mengirim pesan broadcast via UDP ke seluruh LAN"""
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp_sock.sendto(pesan.encode(), (UDP_IP, UDP_PORT))
    udp_sock.close()
    print(f'[UDP] Broadcast terkirim: {pesan}')

@app.route('/')
def index():
    return render_template('index.html', antrian=antrian)

@app.route('/daftar', methods=['GET', 'POST'])
def daftar():
    global nomor_counter
    if request.method == 'POST':
        nama    = request.form['nama']
        jenis   = request.form['jenis']
        email   = request.form['email']
        no_hp   = request.form['no_hp']
        nomor   = nomor_counter
        nomor_counter += 1
        antrian.append({
            'nomor': nomor, 'nama': nama,
            'jenis': jenis, 'email': email,
            'no_hp': no_hp, 'status': 'Menunggu'
        })
        return redirect(url_for('index'))
    return render_template('daftar.html')

@app.route('/admin')
def admin():
    return render_template('admin.html', antrian=antrian)

@app.route('/panggil/<int:nomor>')
def panggil(nomor):
    for item in antrian:
        if item['nomor'] == nomor and item['status'] == 'Menunggu':
            item['status'] = 'Dipanggil'
            pesan = f'[ANTRIAN] Nomor {nomor} - {item["nama"]} ({item["jenis"]}) silahkan ke area cuci!'
            # Broadcast UDP ke LAN
            threading.Thread(target=broadcast_udp, args=(pesan,)).start()
            # Kirim email notifikasi via SMTP/TCP
            threading.Thread(target=kirim_email_notifikasi,
                             args=(item['email'], item['nama'], nomor)).start()
            break
    return redirect(url_for('admin'))

@app.route('/selesai/<int:nomor>')
def selesai(nomor):
    for item in antrian:
        if item['nomor'] == nomor:
            item['status'] = 'Selesai'
            pesan = f'[ANTRIAN] Nomor {nomor} - {item["nama"]} telah selesai. Terima kasih!'
            threading.Thread(target=broadcast_udp, args=(pesan,)).start()
            break
    return redirect(url_for('admin'))

if __name__ == '__main__':
    # Flask berjalan di TCP port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
