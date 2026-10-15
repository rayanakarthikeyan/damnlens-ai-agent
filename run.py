"""Launch the local app. Install requirements.txt first."""
import argparse
import threading
import webbrowser


def main():
    parser=argparse.ArgumentParser(description='LedgerLens local document-to-Excel agent')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    try:import uvicorn
    except ImportError:raise SystemExit('Install dependencies first: python -m pip install -r requirements.txt')
    url=f'http://127.0.0.1:{args.port}'
    print(f'\nLedgerLens is starting at {url}\nYour documents are processed locally. Press Ctrl+C to stop.\n')
    if not args.no_browser:threading.Timer(1.5,lambda:webbrowser.open(url)).start()
    uvicorn.run('app.main:app',host='127.0.0.1',port=args.port,log_level='info')


if __name__=='__main__':main()
