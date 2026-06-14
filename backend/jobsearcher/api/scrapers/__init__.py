from scrapers.base import BaseScraper, Job
from scrapers.remotive import RemotiveScraper
from scrapers.indeed import IndeedScraper
from scrapers.registry import ScraperRegistry

__all__ = ["BaseScraper", "Job", "RemotiveScraper", "IndeedScraper", "ScraperRegistry"]
