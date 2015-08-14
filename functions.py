from config import credentials, status_credentials
import tweepy


def login(REST=True, status=False):
    """ Return api or auth object
    REST -- If True, return REST API only.
    REST -- If "Both", retuns both API and AUTH.
    status -- If True, return REST API of status account.
    """
    if status:
        consumer_token = status_credentials['consumer_key']
        consumer_secret = status_credentials['consumer_secret']
        access_token = status_credentials['access_token']
        access_token_secret = status_credentials['access_token_secret']
    else:
        consumer_token = credentials['consumer_key']
        consumer_secret = credentials['consumer_secret']
        access_token = credentials['access_token']
        access_token_secret = credentials['access_token_secret']

    auth = tweepy.OAuthHandler(consumer_token, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    if REST:
        api = tweepy.API(auth)
        return api
    elif REST == "Both":
        return api, auth
    else:
        return auth
