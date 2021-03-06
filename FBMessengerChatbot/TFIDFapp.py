from flask import Flask, request
from pymessenger.bot import Bot
from FBMessengerChatbot.TFIDF.Transformer import Transformer
import os
from pymongo import MongoClient
from datetime import datetime, timedelta

# define on heroku settings tab
ACCESS_TOKEN = os.environ['ACCESS_TOKEN']
VERIFY_TOKEN = os.environ['VERIFY_TOKEN']
MONGODB_URI = os.environ['MONGODB_URI']

cluster = MongoClient(MONGODB_URI)
db = cluster['QnA']
collection = db['QnA']

# flask app configuration
app = Flask(__name__)
bot = Bot(ACCESS_TOKEN)
transformer = Transformer('FBMessengerChatbot/data/train/QnA.csv',
                          'FBMessengerChatbot/data/train/SimplifiedChineseQnA.csv',
                          'FBMessengerChatbot/data/train/traditionalChineseQnA.csv',
                          'FBMessengerChatbot/data/train/SpanishQnA.csv')


# We will receive messages that Facebook sends our bot at this endpoint
@app.route("/", methods=['GET', 'POST'])
def receive_message():
    if request.method == 'GET':
        """Before allowing people to message your bot, Facebook has implemented a verify token
        that confirms all requests that your bot receives came from Facebook."""
        token_sent = request.args.get("hub.verify_token")
        return verify_fb_token(token_sent)
    # if the request was not get, it must be POST and we can just proceed with sending a message back to user
    else:
        # get whatever message a user sent the bot
        output = request.get_json()
        for event in output['entry']:
            messaging = event['messaging']
            for message in messaging:
                if message.get('message'):
                    # Facebook Messenger ID for user so we know where to send response back to
                    recipient_id = message['sender']['id']
                    if message['message'].get('text'):
                        # NLP detection
                        if message['message'].get('nlp'):
                            try:
                                # detected English
                                if 'en' in message['message']['nlp']['detected_locales'][0]['locale']:
                                    # greeting detected
                                    if message['message']['nlp']['entities'].get('greetings') and \
                                            message['message']['nlp']['entities']['greetings'][0]['confidence'] >= 0.9:
                                        response = "Hello! Nice to meet you!"
                                        bot.send_text_message(recipient_id, response)
                                        insert(message, response)
                                        continue
                                    # bye detected
                                    elif message['message']['nlp']['entities'].get('bye') and \
                                            message['message']['nlp']['entities']['bye'][0]['confidence'] >= 0.9:
                                        response = "See you next time!"
                                        bot.send_text_message(recipient_id, response)
                                        insert(message, response)
                                        continue
                                    # thank detected
                                    elif message['message']['nlp']['entities'].get('thanks') and \
                                            message['message']['nlp']['entities']['thanks'][0]['confidence'] >= 0.9:
                                        response = "You are welcome!"
                                        bot.send_text_message(recipient_id, response)
                                        insert(message, response)
                                        continue
                                # detected Spanish
                                elif 'es' in message['message']['nlp']['detected_locales'][0]['locale']:
                                    # greeting detected
                                    if message['message']['nlp']['entities'].get('greetings') and \
                                            message['message']['nlp']['entities']['greetings'][0]['confidence'] >= 0.6:
                                        response = "¡Mucho gusto! ¿Cómo estás?"
                                        bot.send_text_message(recipient_id, response)
                                        insert(message, response)
                                        continue
                                    elif message['message']['nlp']['entities'].get('bye') and \
                                            message['message']['nlp']['entities']['bye'][0]['confidence'] >= 0.6:
                                        response = "¡Adíos!"
                                        bot.send_text_message(recipient_id, response)
                                        insert(message, response)
                                        continue
                                    elif message['message']['nlp']['entities'].get('thanks') and \
                                            message['message']['nlp']['entities']['thanks'][0]['confidence'] >= 0.6:
                                        response = "¡De nada!"
                                        bot.send_text_message(recipient_id, response)
                                        insert(message, response)
                                        continue
                            except KeyError:
                                print('NLP is not deployed.')

                        response, similarity = transformer.match_query(message['message'].get('text'))

                        # no acceptable answers found in the pool
                        if similarity < 0.5:
                            response = "Please wait! Our representative is on the way to help you!"
                            bot.send_text_message(recipient_id, response)
                        else:
                            responses = response.split('|')
                            for r in responses:
                                if r != '':
                                    bot.send_text_message(recipient_id, r.strip())

                        insert(message, response)
                    # if user sends us a GIF, photo,video, or any other non-text item
                    if message['message'].get('attachments'):
                        i = 0
                        while i < 1:
                            bot.send_text_message(recipient_id, "Interesting! Anything else I could help?")
                            i += 1

                        collection.insert_one({"question": "Non text",
                                               "answer": "Interesting! Anything else I could help?"})

    return "Message Processed"


def verify_fb_token(token_sent):
    # take token sent by facebook and verify it matches the verify token you sent
    # if they match, allow the request, else return an error
    if token_sent == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return 'Connected successfully!'


def insert(message, response):
    # EST
    time = (datetime.fromtimestamp(int(str(message['timestamp'])[:-3])) - timedelta(hours=4)).strftime(
        '%Y-%m-%d %H:%M:%S')
    collection.insert_one({"question": message['message'].get('text'),
                           "answer": response, 'time': time, 'source':'Facebook Messenger'})


if __name__ == "__main__":
    app.run()
