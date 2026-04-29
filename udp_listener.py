import socket

UDP_PORT = 5005

# Membuat socket UDP (connectionless)
# SOCK_DGRAM = socket UDP, berbeda dengan SOCK_STREAM (TCP)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Mengizinkan menerima broadcast
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

# Bind ke semua interface pada port 5005
sock.bind(('', UDP_PORT))

print('[UDP Listener] Mendengarkan notifikasi broadcast dari server...')
print(f'[UDP Listener] Port: {UDP_PORT}')
print('-' * 50)

while True:
    # Menerima data tanpa perlu handshake (connectionless)
    data, addr = sock.recvfrom(1024)
    pesan = data.decode()
    print(f'[NOTIFIKASI] {pesan}')
    print(f'[DARI] Server: {addr[0]}:{addr[1]}')
    print('-' * 50)
