from appwrite.services.databases import Databases
from tweety.bot import Twitter

from dbsetup import tweets
from utils.prep_data import prep_tweet_data


def load_tweets(
    keyword: str,
    search_filter: str,
    db: Databases,
    context: dict,
    max_tweets: int = 100000,
) -> None:
    """
    Scrape tweets from twitter and upload to appwrite database.
    :param keyword: keyword to search for
    :param search_filter: filter to apply to search
    :param db: appwrite database instance
    :param context: context dictionary
    :param max_tweets: maximum number of tweets to scrape
    """
    print("------------------------------------------------")
    print(f"Starting scraper for {keyword}")
    total_scraped = 0
    total_errors = 0
    total_inserted = 0
    total_ignored = 0
    page_number = 0

    # setup collection
    app = Twitter()
    tweets.setup_collection(db, context)

    # search for tweets
    results_cursor = results = app.search(
        keyword=keyword,
        wait_time=5,
        filter_=search_filter,
    )

    # run until max tweets reached or no more results
    while results:
        page_number += 1
        print(f"Scraping page {page_number}...")

        # upload to database
        for tweet in results:
            total_scraped += 1
            print(f"Processing tweet {total_scraped}...")
            upload_data = prep_tweet_data(tweet)

            # ignore retweets, replies, quoted tweets, and possibly sensitive tweets
            if (
                tweet.is_retweet
                or tweet.is_quoted
                or tweet.is_reply
                or tweet.is_possibly_sensitive
            ):
                total_ignored += 1
                continue

            try:
                db.create_document(
                    database_id=context["database_id"],
                    collection_id=context["collection_id"],
                    document_id=tweet.id,
                    data=upload_data,
                )
            except Exception as e:
                # don't count duplicate tweets as errors
                if "requested ID already exists" in str(e):
                    total_ignored += 1
                else:
                    total_errors += 1
                    print("------------------------------------------------")
                    print(upload_data)
                    print(e)
                    print("------------------------------------------------")
            else:
                total_inserted += 1

        print("------------------------------------------------")
        print(f"Page {page_number} scraped.")
        print(f"Total scraped: {total_scraped}")
        print(f"Total inserted: {total_inserted}")
        print(f"Total ignored: {total_ignored}")
        print(f"Total errors: {total_errors}")
        print(f"Do we have next page: {results_cursor.is_next_page}")
        print("------------------------------------------------")

        # check if max tweets reached
        if total_scraped >= max_tweets:
            print("------------------------------------------------")
            print(f"Max tweets reached: {max_tweets}")
            print("------------------------------------------------")
            break

        # check if next page exists
        if not results_cursor.is_next_page:
            print("------------------------------------------------")
            print("No more results.")
            print("------------------------------------------------")
            break

        # get next page of results
        # retry if error fetching next page
        data_fetched = False
        retries = 0
        while not data_fetched:
            try:
                results = results_cursor.get_next_page()
            except Exception:
                print(f"Error fetching next page, retrying...{retries}")
                retries += 1
            else:
                data_fetched = True