from subprocess import call

# Run gunicorn from the current Python environment
call(["python", "-m", "gunicorn", "app:app"])
