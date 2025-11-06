from app import app

if __name__ == '__main__':
    app.logger.info("Starting development server")
    app.run(host='0.0.0.0', port=5025, debug=True)
