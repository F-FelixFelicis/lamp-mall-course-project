"""Keep image-query multipart bodies bounded and in memory, including parser buffers."""
from starlette.formparsers import MultiPartParser
from starlette.responses import JSONResponse

MAX_QUERY_BODY = 6 * 1024 * 1024  # 5 MiB image plus bounded multipart overhead
# Starlette otherwise rolls files over 1 MiB onto disk before the route is called.
# Starlette renamed max_file_size to spool_max_size. Configure the attribute
# actually supported by the installed parser; assigning the newer name on an
# older version silently leaves its 1 MiB rollover threshold unchanged.
# The query middleware caps the complete body at this parser spool threshold.
if hasattr(MultiPartParser, 'spool_max_size'):
    MultiPartParser.spool_max_size = MAX_QUERY_BODY
else:
    MultiPartParser.max_file_size = MAX_QUERY_BODY


class ImageQueryMemoryLimit:
    def __init__(self,app):self.app=app

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope.get('method')!='POST' or scope.get('path')!='/api/v1/search/image':
            await self.app(scope,receive,send);return
        chunks=[];size=0
        while True:
            message=await receive()
            if message['type']=='http.disconnect':return
            chunk=message.get('body',b'');size+=len(chunk)
            if size>MAX_QUERY_BODY:
                response=JSONResponse({'code':'FILE_TOO_LARGE','message':'参考图片不能超过 5 MB，请缩小图片后重试',
                    'request_id':scope.get('state',{}).get('request_id','unknown')},status_code=413)
                await response(scope,receive,send);return
            chunks.append(chunk)
            if not message.get('more_body',False):break
        body=b''.join(chunks);del chunks
        delivered=False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {'type':'http.request','body':body,'more_body':False}
            return await receive()
        await self.app(scope,replay,send)
