import socket
import json
import struct
import os
import time
import traceback
from datetime import datetime


def ensure_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")


# tcp_server.py

def receive_file(client_socket, base_dir="datasets"):
    try:
        # 메타데이터 길이 수신 (4바이트)
        metadata_length_bytes = client_socket.recv(4)
        if not metadata_length_bytes:
            print("Failed to receive metadata length")
            return False

        metadata_size = struct.unpack('!I', metadata_length_bytes)[0]
        print(f"Expected metadata size: {metadata_size}")

        # 메타데이터 수신
        metadata_bytes = b''
        remaining = metadata_size

        while remaining > 0:
            chunk = client_socket.recv(remaining)
            if not chunk:
                break
            metadata_bytes += chunk
            remaining -= len(chunk)

        if len(metadata_bytes) != metadata_size:
            print(f"Incomplete metadata received: {len(metadata_bytes)}/{metadata_size}")
            return False

        metadata_json = metadata_bytes.decode('utf-8')
        print(f"Received metadata: {metadata_json}")

        try:
            metadata = json.loads(metadata_json)
            print(f"Parsed metadata: {metadata}")
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            return False

        # 메타데이터 수신 확인 송신
        client_socket.send(b'OK')

        # 파일 저장 경로 설정
        folder_name = metadata.get('folderName', time.strftime("%Y%m%d_%H%M%S"))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{metadata['fileName']}"

        # 최종 저장 디렉토리 설정 (base_dir/folder_name)
        save_dir = os.path.join(base_dir, folder_name, "images")
        save_path = os.path.join(save_dir, filename)

        # 저장 디렉토리 생성
        ensure_directory(save_dir)

        # 파일 수신 및 저장
        total_received = 0
        file_size = metadata['fileSize']

        with open(save_path, 'wb') as f:
            while total_received < file_size:
                chunk = client_socket.recv(min(32768, file_size - total_received))
                if not chunk:
                    break
                f.write(chunk)
                total_received += len(chunk)
                progress = (total_received / file_size) * 100
                print(f"\rProgress: {progress:.1f}% ({total_received}/{file_size}) -> {save_path}", end='')

        print(f"\nFile saved: {save_path}")

        # 파일 수신 완료 확인 송신
        client_socket.send(b'OK')
        return True

    except Exception as e:
        print(f"Error receiving file: {e}")
        print(f"Stack trace: {traceback.format_exc()}")  # 스택 트레이스 출력
        return False


def start_server(host='0.0.0.0', port=9999, base_dir='datasets'):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((host, port))
    server_socket.listen(5)

    # 기본 저장 디렉토리 생성
    ensure_directory(base_dir)
    print(f"Server listening on {host}:{port}")
    print(f"Base directory for received files: {base_dir}")

    try:
        while True:
            client_socket, addr = server_socket.accept()
            print(f"\nConnected by {addr}")

            try:
                receive_file(client_socket, base_dir)
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
    parser.add_argument('--dir', type=str, default='datasets', help='Base directory to save files')

    args = parser.parse_args()

    print(f"Starting server...")
    print(f"Base directory: {args.dir}")
    start_server(args.host, args.port, args.dir)