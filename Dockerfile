FROM python:3.11.3-bullseye

# Install project dependencies
COPY requirements.txt /bot/
WORKDIR /bot
RUN pip install -r requirements.txt

# Copy the source code in last to optimize rebuilding the image
COPY . .

CMD ["python3", "-m", "bot"]