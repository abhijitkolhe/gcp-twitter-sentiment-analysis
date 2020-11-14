// Package p contains a Pub/Sub Cloud Function.
package p

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"sync"
	"sync/atomic"
	"time"

	"cloud.google.com/go/pubsub"
)

// PubSubMessage is the payload of a Pub/Sub event. Please refer to the docs for additional information regarding Pub/Sub events.
type PubSubMessage struct {
	Data []byte `json:"data"`
}

// TwitterResponse represents JSON response from Twitter Recent API.
type TwitterResponse struct {
	Data []TwitterData `json:"data"`
	Meta TwitterMeta   `json:"meta"`
}

// TwitterData represents JSON object which contains Tweet and it is part of TwitterResponse.
type TwitterData struct {
	CreatedAt string `json:"created_at"`
	Id        string `json:"id"`
	Text      string `json:"text"`
}

// TwitterMeta represents JSON object which contains metadata about response from Twitter Recent API and it is part of TwitterResponse.
type TwitterMeta struct {
	NewestId    string `json:"newest_id"`
	OldestId    string `json:"oldest_id"`
	ResultCount int    `json:"result_count"`
	NextToken   string `json:"next_token"`
}

// CrawlingTwitter sends request to Twitter Recent API every minute and receive results from 2 minutes ago to a minute ago.
func CrawlingTwitter(ctx context.Context, m PubSubMessage) error {
	const baseUrl = "https://api.twitter.com/2/tweets/search/recent"
	const searchingQuery = "corona"
	const maxResults = 10

	// required environment variables
	bearerToken, present := os.LookupEnv("BEARER_TOKEN")
	if !present {
		return fmt.Errorf("BEARER_TOKEN variable is not set. Set it to your Twitter account's Bearer token.")
	}

	projectId, present := os.LookupEnv("GCP_PROJECT")
	if !present {
		return fmt.Errorf("GCP_PROJECT variable is not set.")
	}

	topicId, present := os.LookupEnv("TOPIC_ID")
	if !present {
		return fmt.Errorf("TOPIC_ID variable is not set. Please set it to your Pub/Sub topic ID.")
	}

	curTime := time.Now().UTC()
	// curTime - 2 ~ curTime - 1
	startTime := curTime.Add(time.Duration(-2) * time.Minute)
	endTime := curTime.Add(time.Duration(-1) * time.Minute)

	client := &http.Client{}

	req, err := http.NewRequest("GET", baseUrl, nil)
	if err != nil {
		return fmt.Errorf("Creating new request object failed: %s", err)
	}
	req.Header.Add("Authorization", fmt.Sprintf("Bearer %s", bearerToken))

	// queries based on UTC time
	q := req.URL.Query()
	q.Add("query", searchingQuery)
	q.Add("tweet.fields", "created_at")
	q.Add("start_time", startTime.Format(time.RFC3339))
	q.Add("end_time", endTime.Format(time.RFC3339))
	q.Add("max_results", strconv.Itoa(maxResults))
	req.URL.RawQuery = q.Encode()

	twitterResp := new(TwitterResponse)

	resp, err := client.Do(req)
	defer resp.Body.Close()

	if err != nil {
		return fmt.Errorf("Sending request to Twitter API failed: %s", err)
	}

	json.NewDecoder(resp.Body).Decode(twitterResp)

	pubSubClient, err := pubsub.NewClient(ctx, projectId)
	if err != nil {
		return fmt.Errorf("Creating new client with project ID %d failed: %s")
	}

	var wg sync.WaitGroup
	var errCnt uint64
	t := pubSubClient.Topic(topicId)

	// publish to Pub/Sub
	for _, data := range twitterResp.Data {
		result := t.Publish(ctx, &pubsub.Message{
			Data: []byte(data.Text),
		})
		wg.Add(1)
		go func(res *pubsub.PublishResult) {
			defer wg.Done()
			_, err := res.Get(ctx)
			if err != nil {
				atomic.AddUint64(&errCnt, 1)
				return
			}
		}(result)
	}
	wg.Wait()

	if errCnt > 0 {
		return fmt.Errorf("Publishing %d / %d messages failed.", errCnt, len(twitterResp.Data))
	}
	return nil
}
