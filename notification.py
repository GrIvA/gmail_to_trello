# -*- coding: utf-8 -*-

import os
from re import I
from dotenv import load_dotenv
from trello import TrelloClient
import traceback
from GmailNotificationService.gmail import ReturnMessagesAsGmailModels
from base64 import urlsafe_b64decode
import io

def CreateNewTrelloNotification(message):
    load_dotenv()
    TRELLO_API_KEY = os.environ.get("TRELLO_API_KEY")
    TRELLO_TOKEN = os.environ.get("TRELLO_TOKEN")
    TRELLO_LIST_ID = os.environ.get("TRELLO_LIST_ID")

    client = TrelloClient(api_key=TRELLO_API_KEY, token=TRELLO_TOKEN)

    all_boards = client.list_boards()
    last_board = all_boards[-1]

    my_list = last_board.get_list(TRELLO_LIST_ID)

    card = my_list.add_card(
        'new mail from <%s>' % (message['headers']['From']),
        "Subject: %s\r**************\r%s" % (message['headers']['Subject'], message['decoded_body'])
    )
    if len(message['attach']):
        for att in message['attach']:
            inmemoryfile = io.BytesIO(urlsafe_b64decode(att['data'].encode('UTF-8')))
            card.attach(
                name=att['name'],
                mimeType=att['mime'],
                file=inmemoryfile
            );
            inmemoryfile.close()


def InitiatePushNotification():
    messages_array = ReturnMessagesAsGmailModels()

    try:
        for message in messages_array:
            print(message)
            CreateNewTrelloNotification(message)
            print('Added message from <%s>' % (message['headers']['From']))
    except Exception as err:
        print(traceback.print_exception(err))
