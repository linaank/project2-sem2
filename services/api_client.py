"""
API клиент для работы с Mail.gw
"""

import asyncio
import logging
import random
import string
import time
from typing import Dict, List, Optional, Any
import aiohttp

from config.settings import settings

logger = logging.getLogger(__name__)


class MailGwClient:
    """Клиент для работы с Mail.gw API"""
    
    def __init__(self):
        self.base_url = settings.base_url
        self.session = None
        self.cache = {}
        self.cache_ttl = 60
        
    async def __aenter__(self):
        await self.start_session()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close_session()
        
    async def start_session(self):
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                }
            )
            
    async def close_session(self):
        if self.session and not self.session.closed:
            await self.session.close()
            
    def _is_cache_valid(self, key):
        if key not in self.cache:
            return False
        _, timestamp = self.cache[key]
        return time.time() - timestamp < self.cache_ttl
        
    def _get_from_cache(self, key):
        if self._is_cache_valid(key):
            data, _ = self.cache[key]
            return data
        return None
        
    def _set_cache(self, key, data):
        self.cache[key] = (data, time.time())
        
    async def _make_request(self, method, endpoint, data=None, headers=None):
        await self.start_session()
        
        if not self.session:
            logger.error("HTTP session is not available")
            return None
        
        url = f"{self.base_url}{endpoint}"
        request_headers = {}
        
        if headers:
            request_headers.update(headers)
            
        try:
            logger.info(f"Making {method} request to {url}")
            
            async with self.session.request(
                method=method,
                url=url,
                json=data if data else None,
                headers=request_headers
            ) as response:
                
                if response.status == 200 or response.status == 201:
                    result = await response.json()
                    logger.info(f"Request successful: {response.status}")
                    return result
                else:
                    logger.error(f"Request failed with status {response.status}: {url}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error when requesting {url}: {e}")
            return None
            
    async def get_domains(self):
        cache_key = "domains"
        cached = self._get_from_cache(cache_key)
        if cached:
            logger.info(f"Retrieved domains from cache: {len(cached)} domains")
            return cached
            
        result = await self._make_request("GET", "/domains")
        logger.info(f"Domains API response: {result}")
        
        if result and "hydra:member" in result:
            domains = result["hydra:member"]
            logger.info(f"Found {len(domains)} domains: {[d.get('domain', 'unknown') for d in domains]}")
            self._set_cache(cache_key, domains)
            return domains
        elif result and isinstance(result, list):
            logger.info(f"Domains returned as list: {result}")
            self._set_cache(cache_key, result)
            return result
        
        logger.error(f"No domains found in response: {result}")
        return None
        
    def generate_username(self, length=8):
        letters = string.ascii_lowercase + string.digits
        return ''.join(random.choice(letters) for _ in range(length))
        
    async def generate_email(self):
        logger.info("Generating new email address")
        domains = await self.get_domains()
        
        if not domains:
            logger.error("No domains available for email generation")
            return None
        
        if not isinstance(domains, list) or len(domains) == 0:
            logger.error(f"Invalid domains format: {domains}")
            return None
            
        username = self.generate_username()
        domain = random.choice(domains)
        
        if isinstance(domain, dict):
            if "domain" in domain:
                domain_name = domain["domain"]
            elif "name" in domain:
                domain_name = domain["name"]
            else:
                logger.error(f"Unknown domain format: {domain}")
                return None
        elif isinstance(domain, str):
            domain_name = domain
        else:
            logger.error(f"Invalid domain type: {type(domain)}")
            return None
        
        email = f"{username}@{domain_name}"
        logger.info(f"Generated email: {email}")
        return email
        
    async def create_account(self, email, password):
        data = {
            "address": email,
            "password": password
        }
        
        logger.info(f"Creating account for email: {email}")
        result = await self._make_request("POST", "/accounts", data)
        logger.info(f"Account creation response: {result}")
        return result
        
    async def get_token(self, email, password):
        data = {
            "address": email,
            "password": password
        }
        
        logger.info(f"Getting token for email: {email}")
        result = await self._make_request("POST", "/token", data)
        logger.info(f"Token response: {result}")
        
        if result and "token" in result:
            return result["token"]
        return None
        
    async def get_messages(self, token):
        cache_key = f"messages_{token}"
        # Отключаем кэш для получения актуальных сообщений
        # cached = self._get_from_cache(cache_key)
        # if cached:
        #     logger.info(f"Retrieved messages from cache: {len(cached)} messages")
        #     return cached
            
        headers = {"Authorization": f"Bearer {token}"}
        result = await self._make_request("GET", "/messages", headers=headers)
        
        logger.info(f"Raw API response for messages: {result}")
        
        if result is None:
            logger.warning("API response is None")
            return []
        
        # Проверяем, если это список напрямую (новый формат API)
        if isinstance(result, list):
            logger.info(f"Found {len(result)} messages in direct list format")
            return result
        
        # Проверяем старый формат с hydra:member
        if isinstance(result, dict) and "hydra:member" in result:
            messages = result["hydra:member"]
            logger.info(f"Found {len(messages)} messages in hydra:member format")
            return messages
        
        logger.warning(f"Unexpected response format. Result: {result}")
        return []
    async def get_message(self, message_id, token):
        cache_key = f"message_{message_id}_{token}"
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
            
        headers = {"Authorization": f"Bearer {token}"}
        result = await self._make_request("GET", f"/messages/{message_id}", headers=headers)
        
        if result:
            self._set_cache(cache_key, result)
            return result
        return None
        
    async def delete_account(self, account_id, token):
        """Удаление аккаунта"""
        headers = {"Authorization": f"Bearer {token}"}
        logger.info(f"Deleting account {account_id}")
        
        await self.start_session()
        
        if not self.session:
            logger.error("HTTP session is not available")
            return False
        
        url = f"{self.base_url}/accounts/{account_id}"
        
        try:
            async with self.session.delete(url, headers=headers) as response:
                logger.info(f"Delete account response: status={response.status}")
                
                # Для DELETE запросов успешными считаются коды 200, 204, 404
                # 404 может означать что аккаунт уже удален
                if response.status in [200, 204, 404]:
                    logger.info(f"Account {account_id} deleted successfully")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to delete account. Status: {response.status}, Error: {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error deleting account {account_id}: {e}")
            return False
