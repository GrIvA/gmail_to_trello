# -*- coding: utf-8 -*-

from array import array
from base64 import b64decode
from re import I
import traceback
from GmailNotificationService.gmailConfig import CreateGmailService
import os
from google.api_core import retry
from dotenv import load_dotenv
from GmailNotificationService.gmailConfig import CreateSubscriptionClient, CreateSubscriptionPath


load_dotenv()

service = CreateGmailService()
TOPIC_NAME = os.environ.get("TOPIC_NAME")

subscriber = CreateSubscriptionClient()
subscription_path = CreateSubscriptionPath()
NUM_MESSAGES = 5

global_history_id = None

def SubscribeToUserInbox():
    json = {
        "labelIds": ["UNREAD"],
        "labelFilterAction": "include",
        "topicName": TOPIC_NAME
    }
    try:
        response_object = service.users().watch(userId = "me", body=json).execute()
    except Exception as err:
        print("Error occured: {0}".format(err))
        return {"message": "Error ocuured"}

    try:
        history_id = response_object['historyId']
        global global_history_id
        global_history_id = history_id
        print("global_history_id is {0}".format(history_id))

    except KeyError as err:
        print(traceback.print_exception(err))
        print("An Error Occured. Count not find the key 'historyId' in the response form user.watch ")

    return response_object

def UnsubscribeToUserInbox():
    try:
        print(service.users().stop(userId = "me").execute())
    except Exception as err:
        print("Error occured: {0}".format(err))
        return {"message": "Error ocuured"}

def AttachmentGmailService(message_id, attribute_id):
    try:
        att_object = service.users().messages().attachments().get(userId="me", messageId=message_id, id=attribute_id).execute()
    except Exception as err:
        print("Error occured: {0}".format(err))
        return {"message": "Error ocuured"}

    return att_object

def PollMessages():
    with subscriber:
        response = subscriber.pull(
            request={"subscription": subscription_path, "max_messages": NUM_MESSAGES},
            retry=retry.Retry(deadline=300),
        )
        if len(response.received_messages) == 0:
            return

        return response

def _UpdateLatesHistory(response):
    global global_history_id
    if 'historyId' in response:
        global_history_id = response['historyId']

def ListChanges(startHistoryId: str, userId: str = "me"):
    try:
        response = service.users().history().list(userId = userId,  startHistoryId = startHistoryId).execute()
        return response
    except Exception as err:
        print("Error occured: {0}".format(err))
        return {"message": "Error ocuured"}

def _ExtractMessagesId(response):
#    print(response)
    message_ids = []
    response_array = response['history']
    for item in response_array:
        if 'messagesAdded' in item:
            messages_added = item['messagesAdded']
            for message in messages_added:
                data = message['message']
                if ('labelIds' in data) and ('INBOX' in data['labelIds']):
                    message_ids.append(data['id'])
    return message_ids

def GetMessages(messageIds: array) -> array:
    messages = []

    for id in messageIds:
        try:
            response_object = service.users().messages().get(userId='me', id=id, format ='full').execute()
            messages.append(response_object)
        except:
            pass
    return messages

def ModelFromMessageJSON(json):
    body_decode = lambda d: b64decode(d, '-_').decode('unicode-escape').encode('latin1').decode('utf-8')
    gmail = {'attach': [], 'headers': {}}
    payload = json['payload']
    message_id = json['id']

    try:
        headers = payload['headers']
        gmail['headers']['From'] = [i['value'] for i in headers if i['name']=="From"][0]
        gmail['headers']['Subject'] = [i['value'] for i in headers if i['name']=="Subject"][0]
        gmail['headers']['Content'] = [i['value'] for i in headers if i['name']=="Content-Type"][0]

        body = ''
        if 'body' in payload and payload['body']['size'] > 0:
            body = body_decode(payload['body']['data'])
        else:
            for part in payload['parts']:
                # body
                if 'body' in part and part['body']['size'] > 0 \
                        and 'mimeType' in part and part['mimeType'] == 'text/plain':
                    body = '%s%s' % (body, body_decode(part['body']['data']))

                # attachments
                if 'mimeType' in part and part['mimeType'] != 'text/plain':
                    if part['filename']:
                        if 'data' in part['body']:
                            data=part['body']['data']
                        else:
                            att_id=part['body']['attachmentId']
                            att=AttachmentGmailService(message_id, att_id)
                            data=att['data']

                    gmail['attach'].append({
                        'data': data,
                        'name': part['filename'],
                        'mime': part['mimeType']
                    })

        gmail['decoded_body'] = body

        return gmail
    except KeyError as e:
        print(traceback.print_exception(e))
        return None
    except TypeError as e:
        print(traceback.print_exception(e))
        return None

def AcknowledgeMessages(response):
    ack_ids = []
    try:
        for received_message in response.received_messages:
            print(f"Received: {received_message.message.data}.")
            ack_ids.append(received_message.ack_id)

        subscriber.acknowledge(
            request={"subscription": subscription_path, "ack_ids": ack_ids}
        )
    except Exception as e:
        pass

def ReturnMessagesAsGmailModels() -> array:

    if (global_history_id is None):
        SubscribeToUserInbox()

    messages_array = []
    try:
        recentChanges = ListChanges(global_history_id)
        _UpdateLatesHistory(recentChanges)
        messages = _ExtractMessagesId(recentChanges)

        print("=== new messages ===")
        print(messages)
        for item in GetMessages(messages):
#            print(item)
            gmail = ModelFromMessageJSON(item)
            messages_array.append(gmail)

        return messages_array

    except Exception as e:
        return []

def AcknowledgeAllMessages():
    with subscriber:
        response = subscriber.pull(
            request={"subscription": subscription_path, "max_messages": 1000000},
            retry=retry.Retry(deadline=300),
        )
        if len(response.received_messages) == 0:
            return

        ack_ids = []
        try:
            for received_message in response.received_messages:
                print(f"Received: {received_message.message.data}.")
                ack_ids.append(received_message.ack_id)

            subscriber.acknowledge(
                request={"subscription": subscription_path, "ack_ids": ack_ids}
            )
        except Exception as e:
            pass

