"""Build the local image index from the current live catalogue, without network access."""
from sqlalchemy.orm import Session
from .config import Settings
from .database import make_engine
from .image_index import ImageIndex


def main():
    settings=Settings.from_env()
    engine=make_engine(settings.database_url)
    try:
        with Session(engine) as session:
            index=ImageIndex(settings)
            meta=index.build(session)
            print('Index version:',meta['index_version'])
            print('Images:',len(meta['rows']),'SKUs:',len({x['sku_id'] for x in meta['rows']}))
            print('Model SHA256:',meta['weights_sha256'])
            print('Stored at:',index.path)
    finally:engine.dispose()


if __name__=='__main__':main()
