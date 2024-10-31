# tcp_server.py
import socket
import json
import struct
import os
from datetime import datetime

def ensure_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

def receive_file(client_socket, save_dir="received_files"):
    try:
        # 메타데이터 길이 수신 (4바이트)
        metadata_size = struct.unpack('!I', client_socket.recv(4))[0]

        # 메타데이터 수신
        metadata_json = client_socket.recv(metadata_size).decode('utf-8')
        metadata = json.loads(metadata_json)
        print(f"Receiving file: {metadata}")

        # 메타데이터 수신 확인 송신
        client_socket.send(b'OK')

        # 파일 저장 경로 설정
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{metadata['fileName']}"
        save_path = os.path.join(save_dir, filename)

        # 파일 수신 및 저장
        ensure_directory(save_dir)
        total_received = 0
        file_size = metadata['fileSize']

        with open(save_path, 'wb') as f:
            while total_received < file_size:
                # 32KB씩 수신
                chunk = client_socket.recv(32768)
                if not chunk:
                    break
                f.write(chunk)
                total_received += len(chunk)
                # 진행상황 출력
                progress = (total_received / file_size) * 100
                print(f"\rProgress: {progress:.1f}% ({total_received}/{file_size})", end='')

        print(f"\nFile saved: {save_path}")

        # 파일 수신 완료 확인 송신
        client_socket.send(b'OK')
        return True

    except Exception as e:
        print(f"Error receiving file: {e}")
        return False

def start_server(host='0.0.0.0', port=9999):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)

    print(f"Server listening on {host}:{port}")

    try:
        while True:
            client_socket, addr = server_socket.accept()
            print(f"\nConnected by {addr}")

            try:
                receive_file(client_socket)
            except Exception as e:
                print(f"Error handling client: {e}")
            finally:
                client_socket.close()

    except KeyboardInterrupt:
        print("\nServer shutting down...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='TCP File Receiver Server')
    parser.add_argument('--port', type=int, default=9999, help='Port to listen on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--dir', type=str, default='received_files', help='Directory to save files')

    args = parser.parse_args()

    print(f"Starting server...")
    print(f"Save directory: {args.dir}")
    start_server(args.host, args.port)