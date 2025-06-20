"""
Pokemon TCG Bot Backend - Railway Deployment
FastAPI backend for managing Pokemon TCG social media bot
Enhanced with post approval workflow and frontend integration
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional, Union
import os
import json
import uvicorn
from datetime import datetime, timedelta
import asyncio
import logging
import sys

# Configure logging for Railway
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Log startup info
logger.info("Starting Pokemon TCG Bot API...")
logger.info(f"Python version: {sys.version}")
logger.info(f"PORT environment variable: {os.environ.get('PORT', 'Not set')}")

# Twitter API imports and setup
try:
    import tweepy
    import time
    logger.info("Successfully imported tweepy")
except ImportError as e:
    logger.warning(f"Could not import tweepy: {e}")
    tweepy = None

# Add a simple cache to prevent excessive API calls
twitter_cache = {
    "data": None,
    "last_fetch": None,
    "cache_duration": 3600  # 1 hour cache instead of 5 minutes
}

def get_twitter_client():
    """Initialize Twitter API client"""
    try:
        if not tweepy:
            logger.warning("Tweepy not available")
            return None
            
        bearer_token = os.environ.get("TWITTER_BEARER_TOKEN")
        api_key = os.environ.get("TWITTER_API_KEY")
        api_secret = os.environ.get("TWITTER_API_SECRET")
        access_token = os.environ.get("TWITTER_ACCESS_TOKEN")
        access_secret = os.environ.get("TWITTER_ACCESS_SECRET")
        
        if not all([bearer_token, api_key, api_secret, access_token, access_secret]):
            logger.warning("Twitter API credentials not fully configured")
            return None
            
        # Create client WITHOUT wait_on_rate_limit to prevent blocking
        client = tweepy.Client(
            bearer_token=bearer_token,
            consumer_key=api_key,
            consumer_secret=api_secret,
            access_token=access_token,
            access_token_secret=access_secret,
            wait_on_rate_limit=False  # Changed from True to False
        )
        
        return client
    except Exception as e:
        logger.error(f"Error creating Twitter client: {e}")
        return None

def get_date_range(days_back: int = 7):
    """Get date range for Twitter API queries"""
    end_time = datetime.now()
    start_time = end_time - timedelta(days=days_back)
    return start_time, end_time

def calculate_growth_rate(current_data: list, previous_data: list) -> float:
    """Calculate growth rate between two periods"""
    try:
        current_total = sum(current_data) if current_data else 0
        previous_total = sum(previous_data) if previous_data else 0
        
        if previous_total == 0:
            return 0.0
        
        growth = ((current_total - previous_total) / previous_total) * 100
        return round(growth, 1)
    except:
        return 0.0

def get_mock_twitter_metrics():
    """Return mock data when Twitter API is not available"""
    return {
        "posts": {
            "today": 3,
            "change": "+1 from yesterday",
            "chartData": [8, 6, 10, 12, 9, 15, 12]
        },
        "likes": {
            "total": 234,
            "change": "+18% this week",
            "chartData": [180, 195, 210, 225, 200, 220, 234]
        },
        "replies": {
            "total": 18,
            "change": "+2 from yesterday", 
            "chartData": [12, 14, 16, 15, 20, 16, 18]
        },
        "growth": {
            "rate": 15.0,
            "change": "vs last week",
            "chartData": [5, 8, 12, 10, 15, 13, 15]
        },
        "timestamp": datetime.now().isoformat(),
        "success": True,
        "mock": True
    }

# Import your existing modules with error handling
try:
    from bot_manager import BotManager
    logger.info("Successfully imported BotManager")
except ImportError as e:
    logger.warning(f"Could not import BotManager: {e}")
    # Create a dummy BotManager for Railway deployment
    class BotManager:
        def get_status(self): return {"status": "ok"}
        def get_all_jobs(self): return []
        def create_job(self, job_type, settings): return {"id": "dummy", "type": job_type}
        def create_job_with_approval(self, settings): return {"posts": [], "job_settings": settings}
        def get_job(self, job_id): return {"id": job_id, "status": "stopped"}
        def start_job(self, job_id): pass
        def stop_job(self, job_id): return {"id": job_id, "status": "stopped"}
        def pause_job(self, job_id): return {"id": job_id, "status": "paused"}
        def update_job(self, job_id, job): pass
        def get_metrics(self): return {"totalPosts": 0, "avgEngagement": 0}
        def get_posts(self, limit, offset): return {"posts": [], "total": 0, "hasMore": False}
        def get_topics(self): return []
        def get_engagement_data(self, days): return []
        def get_settings(self): return {"postsPerDay": 12, "keywords": ["Pokemon", "TCG"]}
        def update_settings(self, settings): return settings
        def store_generated_posts(self, posts, settings): return True
        def get_generated_posts(self): return []
        def approve_post(self, post_id): return True
        def reject_post(self, post_id): return True
        def schedule_approved_posts(self): return {"scheduled_count": 0}

try:
    from src.content_generator import generate_viral_content, optimize_content_for_engagement
    logger.info("Successfully imported content generation modules")
except ImportError as e:
    logger.warning(f"Could not import content generators: {e}")
    # Create dummy functions
    def generate_viral_content(count=1):
        return [{"content": "Sample Pokemon TCG content", "engagement_score": 0.8}] * count
    def optimize_content_for_engagement(content):
        return content

try:
    from src.twitter_poster import post_original_tweet, get_tweet_url
    logger.info("Successfully imported Twitter modules")
except ImportError as e:
    logger.warning(f"Could not import Twitter modules: {e}")
    # Create dummy functions
    def post_original_tweet(content):
        return {"success": False, "error": "Twitter integration not available"}
    def get_tweet_url(tweet_id):
        return f"https://twitter.com/i/status/{tweet_id}"

try:
    from knowledge_manager import update_knowledge_base_from_csv, update_knowledge_base_from_web
    logger.info("Successfully imported knowledge manager")
except ImportError as e:
    logger.warning(f"Could not import knowledge manager: {e}")

app = FastAPI(
    title="Pokemon TCG Bot API", 
    version="1.0.0",
    description="FastAPI backend for managing Pokemon TCG social media bot",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enhanced CORS configuration for Railway + Netlify
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "https://localhost:3000",
    "https://localhost:5173",
]

# Add Netlify origins from environment variables
netlify_url = os.environ.get("NETLIFY_URL")
if netlify_url:
    allowed_origins.append(netlify_url)
    logger.info(f"Added Netlify URL to CORS origins: {netlify_url}")

# Add any additional frontend URLs
frontend_url = os.environ.get("FRONTEND_URL")
if frontend_url:
    allowed_origins.append(frontend_url)
    logger.info(f"Added frontend URL to CORS origins: {frontend_url}")

# For development, allow all origins if specified
if os.environ.get("ALLOW_ALL_ORIGINS", "false").lower() == "true":
    allowed_origins = ["*"]
    logger.info("CORS configured to allow all origins (development mode)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,  # Set to False when using allow_origins=["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
    expose_headers=["*"],
)

# Global bot manager instance
bot_manager = BotManager()

# Enhanced Pydantic models for request/response
class ContentTypes(BaseModel):
    cardPulls: bool = True
    deckBuilding: bool = True
    marketAnalysis: bool = True
    tournaments: bool = False

class ReplyTypes(BaseModel):
    helpful: bool = True
    engaging: bool = True
    promotional: bool = False

class JobSettings(BaseModel):
    postsPerDay: int = 12
    topics: List[str] = ["Pokemon TCG"]
    postingTimeStart: str = "09:00"
    postingTimeEnd: str = "17:00"
    contentTypes: ContentTypes = ContentTypes()
    keywords: List[str] = ["Pokemon", "TCG", "Charizard", "Pikachu"]
    maxRepliesPerHour: int = 10
    replyTypes: ReplyTypes = ReplyTypes()
    # New fields for approval workflow
    approvedPosts: Optional[List[Dict[str, Any]]] = None
    autoPost: bool = False

class CreateJobRequest(BaseModel):
    type: str  # "posting" or "replying"
    settings: JobSettings

class CreateJobWithApprovalRequest(BaseModel):
    postsPerDay: int
    topics: List[str]
    postingTimeStart: str
    postingTimeEnd: str
    contentTypes: ContentTypes

class GeneratedPost(BaseModel):
    id: str
    content: str
    topic: str
    approved: Optional[bool] = None  # null = pending, true = approved, false = rejected
    scheduledTime: Optional[str] = None
    engagement_score: Optional[float] = None
    hashtags: Optional[List[str]] = None
    mentions_tradeup: Optional[bool] = None

class PostApprovalRequest(BaseModel):
    postId: str
    approved: bool

class SchedulePostsRequest(BaseModel):
    approvedPostIds: List[str]

class GenerateContentRequest(BaseModel):
    topic: Optional[str] = None
    keywords: Optional[List[str]] = None
    count: int = 1

class PostToTwitterRequest(BaseModel):
    content: str

# Startup event
@app.on_event("startup")
async def startup_event():
    logger.info("Pokemon TCG Bot API is starting up...")
    logger.info(f"Environment: {os.environ.get('RAILWAY_ENVIRONMENT', 'unknown')}")
    logger.info(f"Service ID: {os.environ.get('RAILWAY_SERVICE_ID', 'unknown')}")
    logger.info(f"Deployment ID: {os.environ.get('RAILWAY_DEPLOYMENT_ID', 'unknown')}")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Pokemon TCG Bot API is shutting down...")

# Add a middleware to handle CORS manually for better control
@app.middleware("http")
async def cors_handler(request, call_next):
    # Log incoming requests for debugging
    logger.info(f"Incoming request: {request.method} {request.url}")
    
    # Handle preflight requests
    if request.method == "OPTIONS":
        response = JSONResponse(content={"message": "OK"})
        origin = request.headers.get("origin")
        
        if allowed_origins == ["*"] or (origin and origin in allowed_origins):
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
        else:
            response.headers["Access-Control-Allow-Origin"] = "*"
            
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Max-Age"] = "86400"
        return response
    
    # Process the request
    try:
        response = await call_next(request)
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        response = JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)}
        )
    
    # Add CORS headers to all responses
    origin = request.headers.get("origin")
    if allowed_origins == ["*"] or (origin and origin in allowed_origins):
        response.headers["Access-Control-Allow-Origin"] = origin or "*"
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
        
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    
    return response

# Health check endpoint - CRITICAL for Railway
@app.get("/health")
async def health_check():
    """Health check endpoint for Railway and monitoring"""
    try:
        # Test bot manager
        status = bot_manager.get_status()
        
        return {
            "status": "healthy", 
            "timestamp": datetime.now().isoformat(),
            "service": "Pokemon TCG Bot API",
            "version": "1.0.0",
            "environment": os.environ.get("RAILWAY_ENVIRONMENT", "unknown"),
            "port": os.environ.get("PORT", "unknown"),
            "bot_manager": "connected" if status else "disconnected",
            "cors": "enabled",
            "uptime": "active"
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "degraded",
            "timestamp": datetime.now().isoformat(),
            "service": "Pokemon TCG Bot API",
            "version": "1.0.0",
            "error": str(e),
            "cors": "enabled"
        }

# Root endpoint - CRITICAL for Railway
@app.get("/")
async def root():
    """Root endpoint - Railway deployment check"""
    return {
        "message": "Pokemon TCG Bot API", 
        "status": "running", 
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "cors": "enabled",
        "environment": os.environ.get("RAILWAY_ENVIRONMENT", "unknown"),
        "timestamp": datetime.now().isoformat()
    }

# NEW: Twitter Metrics Endpoint with Rate Limiting Protection
@app.get("/api/twitter-metrics")
async def get_twitter_metrics():
    """Get real Twitter metrics for dashboard with caching and rate limiting protection"""
    try:
        # Check cache first
        now = datetime.now()
        if (twitter_cache["data"] and 
            twitter_cache["last_fetch"] and 
            (now - twitter_cache["last_fetch"]).seconds < twitter_cache["cache_duration"]):
            
            logger.info("🔄 Returning cached Twitter metrics")
            return twitter_cache["data"]
        
        client = get_twitter_client()
        if not client:
            logger.info("Twitter API not configured, returning mock data")
            return get_mock_twitter_metrics()
        
        user_id = os.environ.get("TWITTER_USER_ID")
        if not user_id:
            logger.warning("TWITTER_USER_ID not configured, returning mock data")
            return get_mock_twitter_metrics()
        
        # Rate limiting check - if we hit rate limit recently, return cached data
        try:
            # ULTRA minimal API usage - only get last 5 tweets
            start_time, end_time = get_date_range(3)  # Only last 3 days instead of 7
            
            # Minimal request to stay under rate limits
            tweets = client.get_users_tweets(
                id=user_id,
                max_results=5,  # Absolute minimum
                tweet_fields=['public_metrics', 'created_at'],
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat()
            )
            
            if not tweets.data:
                logger.info("No tweets found in the specified time range, using cached or mock data")
                if twitter_cache["data"]:
                    return twitter_cache["data"]
                else:
                    return get_mock_twitter_metrics()
            
            # Process tweets by day
            daily_data = {}
            total_likes = 0
            total_replies = 0
            today = datetime.now().date()
            
            for tweet in tweets.data:
                tweet_date = tweet.created_at.date()
                days_ago = (today - tweet_date).days
                
                if days_ago <= 7:
                    if days_ago not in daily_data:
                        daily_data[days_ago] = {
                            'posts': 0,
                            'likes': 0,
                            'replies': 0
                        }
                    
                    daily_data[days_ago]['posts'] += 1
                    daily_data[days_ago]['likes'] += tweet.public_metrics['like_count']
                    daily_data[days_ago]['replies'] += tweet.public_metrics['reply_count']
                    
                    total_likes += tweet.public_metrics['like_count']
                    total_replies += tweet.public_metrics['reply_count']
            
            # Create 7-day arrays (0 = today, 6 = 6 days ago)
            posts_7_days = [daily_data.get(i, {}).get('posts', 0) for i in range(7)]
            likes_7_days = [daily_data.get(i, {}).get('likes', 0) for i in range(7)]
            replies_7_days = [daily_data.get(i, {}).get('replies', 0) for i in range(7)]
            
            # Skip growth rate calculation to avoid additional API calls
            growth_rate = 15.0  # Use static value to avoid rate limits
            
            # Format response to match PostingTrends expectations
            response = {
                "posts": {
                    "today": posts_7_days[0],
                    "change": f"+{posts_7_days[0] - posts_7_days[1]} from yesterday" if len(posts_7_days) > 1 else "+0 from yesterday",
                    "chartData": list(reversed(posts_7_days))  # Reverse so oldest is first
                },
                "likes": {
                    "total": total_likes,
                    "change": f"+{((total_likes - sum(likes_7_days[1:])) / max(sum(likes_7_days[1:]), 1) * 100):.0f}% this week" if sum(likes_7_days[1:]) > 0 else "+0% this week",
                    "chartData": list(reversed(likes_7_days))
                },
                "replies": {
                    "total": total_replies,
                    "change": f"+{replies_7_days[0] - replies_7_days[1]} from yesterday" if len(replies_7_days) > 1 else "+0 from yesterday",
                    "chartData": list(reversed(replies_7_days))
                },
                "growth": {
                    "rate": growth_rate,
                    "change": "vs last week",
                    "chartData": [max(0, growth_rate + i*2) for i in range(-3, 4)]  # Mock growth trend
                },
                "timestamp": datetime.now().isoformat(),
                "success": True,
                "mock": False
            }
            
            # Cache the result
            twitter_cache["data"] = response
            twitter_cache["last_fetch"] = now
            
            logger.info(f"Successfully fetched Twitter metrics: {posts_7_days[0]} posts today, {total_likes} total likes")
            return response
            
        except Exception as twitter_error:
            logger.warning(f"Twitter API error: {twitter_error}")
            # Return cached data if available, otherwise mock data
            if twitter_cache["data"]:
                logger.info("🔄 Returning cached data due to API error")
                return twitter_cache["data"]
            else:
                logger.info("📊 Returning mock data due to API error")
                return get_mock_twitter_metrics()
        
    except Exception as e:
        logger.error(f"Error fetching Twitter metrics: {e}")
        return get_mock_twitter_metrics()

# Bot status endpoints
@app.get("/api/bot-status")
async def get_bot_status():
    """Get current bot status and running jobs"""
    try:
        status = bot_manager.get_status()
        jobs = bot_manager.get_all_jobs()
        
        return {
            "running": any(job["status"] == "running" for job in jobs if isinstance(job, dict) and "status" in job),
            "uptime": "Active" if jobs else None,
            "lastRun": max([job.get("lastRun") for job in jobs if isinstance(job, dict) and job.get("lastRun")], default=None),
            "stats": {
                "postsToday": sum(job.get("stats", {}).get("postsToday", 0) for job in jobs if isinstance(job, dict)),
                "repliesToday": sum(job.get("stats", {}).get("repliesToday", 0) for job in jobs if isinstance(job, dict)),
                "successRate": status.get("stats", {}).get("successRate", 100) if isinstance(status, dict) else 100
            },
            "jobs": jobs,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting bot status: {e}")
        # Return default status instead of error
        return {
            "running": False,
            "uptime": None,
            "lastRun": None,
            "stats": {
                "postsToday": 0,
                "repliesToday": 0,
                "successRate": 100
            },
            "jobs": [],
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

# Enhanced Job management endpoints
@app.post("/api/bot-job/create")
async def create_job(request: CreateJobRequest):
    """Create a new bot job - supports both regular and approval workflow"""
    try:
        # Check if this is an approval workflow job
        if (request.type == "posting" and 
            hasattr(request.settings, 'approvedPosts') and 
            request.settings.approvedPosts is not None):
            
            # This is a job with pre-approved posts
            logger.info("Creating job with pre-approved posts")
            job = bot_manager.create_job(request.type, request.settings.dict())
            
        else:
            # Regular job creation
            logger.info(f"Creating regular {request.type} job")
            job = bot_manager.create_job(request.type, request.settings.dict())
        
        logger.info(f"Created job: {job}")
        return {"success": True, "job": job, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Error creating job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bot-job/create-with-approval")
async def create_job_with_approval(request: CreateJobWithApprovalRequest):
    """Create a job with post approval workflow - generates posts for review"""
    try:
        logger.info("Creating job with approval workflow...")
        
        # Generate posts for approval
        generated_posts = []
        
        for i in range(request.postsPerDay):
            # Select random topic
            import random
            topic = random.choice(request.topics) if request.topics else "Pokemon TCG"
            
            # Generate content
            try:
                content_result = generate_viral_content(count=1, topic=topic)
                if content_result and len(content_result) > 0:
                    content_data = content_result[0]
                    
                    # Generate scheduled time
                    start_time = request.postingTimeStart
                    end_time = request.postingTimeEnd
                    scheduled_time = generate_scheduled_time(i, request.postsPerDay, start_time, end_time)
                    
                    post = {
                        "id": f"post-{int(datetime.now().timestamp())}-{i}",
                        "content": content_data.get("content", f"Great Pokemon TCG content about {topic}!"),
                        "topic": topic,
                        "approved": None,  # Pending approval
                        "scheduledTime": scheduled_time,
                        "engagement_score": content_data.get("engagement_score", 0.75),
                        "hashtags": content_data.get("hashtags", ["#PokemonTCG", "#Trading"]),
                        "mentions_tradeup": "TradeUp" in content_data.get("content", "")
                    }
                    
                    generated_posts.append(post)
                    
            except Exception as content_error:
                logger.error(f"Error generating content for post {i}: {content_error}")
                # Create fallback post
                scheduled_time = generate_scheduled_time(i, request.postsPerDay, request.postingTimeStart, request.postingTimeEnd)
                fallback_post = {
                    "id": f"post-{int(datetime.now().timestamp())}-{i}",
                    "content": f"Exciting Pokemon TCG insights about {topic}! What's your favorite strategy?",
                    "topic": topic,
                    "approved": None,
                    "scheduledTime": scheduled_time,
                    "engagement_score": 0.7,
                    "hashtags": ["#PokemonTCG", "#Trading"],
                    "mentions_tradeup": False
                }
                generated_posts.append(fallback_post)
        
        # Store generated posts in bot manager for approval workflow
        if hasattr(bot_manager, 'store_generated_posts'):
            bot_manager.store_generated_posts(generated_posts, request.dict())
        
        logger.info(f"Generated {len(generated_posts)} posts for approval")
        
        return {
            "success": True,
            "posts": generated_posts,
            "settings": request.dict(),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error creating job with approval: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def generate_scheduled_time(index: int, total_posts: int, start_time: str, end_time: str) -> str:
    """Generate scheduled posting time"""
    try:
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        total_minutes = end_minutes - start_minutes
        
        if total_posts > 1:
            interval = total_minutes // total_posts
            post_time = start_minutes + (interval * index)
        else:
            post_time = start_minutes
        
        hour = post_time // 60
        minute = post_time % 60
        
        return f"{hour:02d}:{minute:02d}"
    except:
        return "12:00"  # Fallback time

# Post approval endpoints
@app.get("/api/generated-posts")
async def get_generated_posts():
    """Get posts pending approval"""
    try:
        if hasattr(bot_manager, 'get_generated_posts'):
            posts = bot_manager.get_generated_posts()
        else:
            posts = []
        
        return {
            "success": True,
            "posts": posts,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting generated posts: {e}")
        return {
            "success": False,
            "posts": [],
            "error": str(e)
        }

@app.post("/api/approve-post")
async def approve_post(request: PostApprovalRequest):
    """Approve or reject a generated post"""
    try:
        if hasattr(bot_manager, 'approve_post' if request.approved else 'reject_post'):
            if request.approved:
                result = bot_manager.approve_post(request.postId)
            else:
                result = bot_manager.reject_post(request.postId)
        else:
            result = True  # Fallback
        
        return {
            "success": True,
            "postId": request.postId,
            "approved": request.approved,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error approving/rejecting post: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/schedule-approved-posts")
async def schedule_approved_posts():
    """Schedule all approved posts as a new job"""
    try:
        if hasattr(bot_manager, 'schedule_approved_posts'):
            result = bot_manager.schedule_approved_posts()
        else:
            result = {"scheduled_count": 0}
        
        logger.info(f"Scheduled approved posts: {result}")
        
        return {
            "success": True,
            "scheduled_count": result.get("scheduled_count", 0),
            "job_id": result.get("job_id"),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error scheduling approved posts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bot-job/{job_id}/start")
async def start_job(job_id: str, background_tasks: BackgroundTasks):
    """Start a bot job"""
    try:
        job = bot_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Start the job in the background
        background_tasks.add_task(bot_manager.start_job, job_id)
        
        # Update job status immediately
        if isinstance(job, dict):
            job["status"] = "running"
            job["lastRun"] = datetime.now().isoformat()
            bot_manager.update_job(job_id, job)
        
        logger.info(f"Started job: {job_id}")
        return {"success": True, "message": "Job started successfully", "job": job}
    except Exception as e:
        logger.error(f"Error starting job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bot-job/{job_id}/stop")
async def stop_job(job_id: str):
    """Stop a bot job"""
    try:
        job = bot_manager.stop_job(job_id)
        logger.info(f"Stopped job: {job_id}")
        return {"success": True, "message": "Job stopped successfully", "job": job}
    except Exception as e:
        logger.error(f"Error stopping job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/bot-job/{job_id}/pause")
async def pause_job(job_id: str):
    """Pause a bot job"""
    try:
        job = bot_manager.pause_job(job_id)
        logger.info(f"Paused job: {job_id}")
        return {"success": True, "message": "Job paused successfully", "job": job}
    except Exception as e:
        logger.error(f"Error pausing job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Content generation endpoints
@app.post("/api/generate-content")
async def generate_content(request: GenerateContentRequest):
    """Generate Pokemon TCG content"""
    try:
        logger.info(f"Generating content with request: {request}")
        
        # Generate viral content using your existing system
        viral_posts = generate_viral_content(request.count)
        
        if not viral_posts:
            logger.error("Failed to generate content - no posts returned")
            return {
                "success": False,
                "error": "Failed to generate content",
                "content": None,
                "timestamp": datetime.now().isoformat()
            }
        
        logger.info(f"Generated {len(viral_posts)} posts")
        
        # Optimize content for engagement
        for post in viral_posts:
            if isinstance(post, dict) and 'content' in post:
                post['optimized_content'] = optimize_content_for_engagement(post['content'])
        
        result = {
            "success": True,
            "content": viral_posts[0] if request.count == 1 else viral_posts,
            "generated_at": datetime.now().isoformat(),
            "count": len(viral_posts)
        }
        
        logger.info(f"Returning content result with {len(viral_posts)} posts")
        return result
        
    except Exception as e:
        logger.error(f"Error generating content: {e}")
        return {
            "success": False,
            "error": str(e),
            "content": None,
            "timestamp": datetime.now().isoformat()
        }

# Twitter posting endpoints
@app.post("/api/post-to-twitter")
async def post_to_twitter(request: PostToTwitterRequest):
    """Post content to Twitter"""
    try:
        logger.info(f"Posting to Twitter: {request.content[:50]}...")
        
        result = post_original_tweet(request.content)
        
        if isinstance(result, dict) and result.get('success'):
            # Add tweet URL if available
            if result.get('tweet_id'):
                result['url'] = get_tweet_url(result['tweet_id'])
                logger.info(f"Successfully posted tweet: {result['url']}")
        else:
            logger.error(f"Failed to post tweet: {result.get('error') if isinstance(result, dict) else 'Unknown error'}")
        
        if isinstance(result, dict):
            result['timestamp'] = datetime.now().isoformat()
        
        return result
    except Exception as e:
        logger.error(f"Error posting to Twitter: {e}")
        return {
            "success": False,
            "error": str(e),
            "tweet_id": None,
            "timestamp": datetime.now().isoformat()
        }

# Data endpoints (for dashboard) - keeping your existing ones
@app.get("/api/metrics")
async def get_metrics():
    """Get bot metrics"""
    try:
        metrics = bot_manager.get_metrics()
        if isinstance(metrics, dict):
            metrics['timestamp'] = datetime.now().isoformat()
        return metrics
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        # Return default metrics instead of error
        return {
            "totalPosts": 0,
            "avgEngagement": 0,
            "totalLikes": 0,
            "followers": 0,
            "lastUpdated": datetime.now().isoformat(),
            "error": str(e)
        }

@app.get("/api/posts")
async def get_posts(limit: int = 20, offset: int = 0):
    """Get recent posts"""
    try:
        posts = bot_manager.get_posts(limit, offset)
        return posts
    except Exception as e:
        logger.error(f"Error getting posts: {e}")
        # Return empty posts instead of error
        return {
            "posts": [], 
            "total": 0, 
            "hasMore": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.get("/api/topics")
async def get_topics():
    """Get trending topics"""
    try:
        topics = bot_manager.get_topics()
        return topics if topics else []
    except Exception as e:
        logger.error(f"Error getting topics: {e}")
        # Return empty topics instead of error
        return []

@app.get("/api/engagement")
async def get_engagement(days: int = 7):
    """Get engagement data"""
    try:
        engagement = bot_manager.get_engagement_data(days)
        return engagement if engagement else []
    except Exception as e:
        logger.error(f"Error getting engagement data: {e}")
        # Return empty engagement data instead of error
        return []

@app.get("/api/settings")
async def get_settings():
    """Get bot settings"""
    try:
        settings = bot_manager.get_settings()
        return settings
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        # Return default settings instead of error
        return {
            "postsPerDay": 12,
            "keywords": ["Pokemon", "TCG", "Charizard", "Pikachu"],
            "engagementMode": "balanced",
            "autoReply": True,
            "contentTypes": {
                "cardPulls": True,
                "deckBuilding": True,
                "marketAnalysis": True,
                "tournaments": True
            },
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

@app.post("/api/settings")
async def update_settings(settings: dict):
    """Update bot settings"""
    try:
        updated_settings = bot_manager.update_settings(settings)
        logger.info(f"Updated settings: {settings}")
        return {
            "success": True, 
            "settings": updated_settings,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return {
            "success": False, 
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
    
@app.get('/debug-twitter-config')
def debug_twitter_config():
    return {
        'api_key_prefix': os.getenv('TWITTER_API_KEY', 'NOT_FOUND')[:10] + '...',
        'access_token_prefix': os.getenv('TWITTER_ACCESS_TOKEN', 'NOT_FOUND')[:15] + '...',
        'bearer_token_prefix': os.getenv('TWITTER_BEARER_TOKEN', 'NOT_FOUND')[:15] + '...',
        'user_id': os.getenv('TWITTER_USER_ID', 'NOT_FOUND'),
        'api_secret_present': bool(os.getenv('TWITTER_API_SECRET')),
        'access_secret_present': bool(os.getenv('TWITTER_ACCESS_SECRET')),
        'all_vars_present': bool(
            os.getenv('TWITTER_API_KEY') and 
            os.getenv('TWITTER_ACCESS_TOKEN') and 
            os.getenv('TWITTER_BEARER_TOKEN') and
            os.getenv('TWITTER_USER_ID') and
            os.getenv('TWITTER_API_SECRET') and
            os.getenv('TWITTER_ACCESS_SECRET')
        )
    }

# Railway requires this exact pattern
if __name__ == "__main__":
    # Get port from environment (Railway sets this automatically)
    port = int(os.environ.get("PORT", 8000))
    
    logger.info(f"Starting server on host 0.0.0.0, port {port}")
    logger.info(f"Environment variables loaded: PORT={port}")
    
    # Railway deployment configuration
    uvicorn.run(
        app, 
        host="0.0.0.0",  # Must bind to all interfaces for Railway
        port=port,       # Must use Railway's PORT
        log_level="info",
        access_log=True,
        server_header=False,
        date_header=False
    )