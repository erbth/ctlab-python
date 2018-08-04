import ctlab
import asyncio

async def worker(loop):
    try:
        lab2 = ctlab.AsyncIO_Connection(loop,'ct-lab2', 10001)
        await lab2.connect()
    except Exception as e:
        print('Cannot connect to ct-lab2: %s' % e)
        exit(1)

    dcg = ctlab.DCG(1,lab2)
    dcg.set_dcv(10)

    await asyncio.sleep(1)

    await lab2.receive()

    lab2.close()

loop = asyncio.get_event_loop()
loop.run_until_complete(worker(loop))
loop.close()
