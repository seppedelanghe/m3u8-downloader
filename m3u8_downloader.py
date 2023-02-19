import os
import cv2
import time
import requests
import argparse

from tqdm import tqdm
from threading import Thread
from queue import Queue, Empty
from typing import List, Tuple, Dict, Any


parser = argparse.ArgumentParser()
parser.add_argument('--url', type=str, required=True, help='The url of the m3u8 playlist file')
parser.add_argument('--out', type=str, required=True, help='Where should the video be saved to')
parser.add_argument('--fourcc', type=str, required=False, help='Fourcc to use, default mp4v, see cv2 supported fourccs for more options', default='mp4v')
parser.add_argument('--threads', type=int, required=False, help='The amount of concurrent threads to use to retreive the video', default=4)
parser.add_argument('--view', type=bool, required=False, help='View the video as it is downloading, this will considerably slow down the download.', action=argparse.BooleanOptionalAction, default=False)


class PartReader(Thread):
    def __init__(self, url: str, writer: Queue) -> None:
        super().__init__()

        self.url = url
        self.writer = writer

    def run(self):
        try:
            cap = cv2.VideoCapture(self.url)
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                self.writer.put(frame)
            cap.release()
        except Exception:
            raise


class M3U8Downloader:
    def __init__(self, m3u8_url: str, threads: int = 4, display: bool = False):
        self.base_url = m3u8_url.replace(os.path.basename(m3u8_url), '')
        self.m3u8_file = os.path.basename(m3u8_url)
        self.threads = threads

        # does not provide a stable watching experience, more for debugging
        self.display = display

    @property
    def m3u8_url(self) -> str:
        return os.path.join(self.base_url, self.m3u8_file)
    
    def _part_url(self, filename: str) -> str:
        return os.path.join(self.base_url, filename)

    def _read_m3u8(self) -> List[Dict[str, Any]]:
        r = requests.get(self.m3u8_url)
        if r.status_code != 200:
            raise Exception(f"Invalid m3u8 url, cannot open url: {self.m3u8_url}")
        
        res, t = [], {}
        for idx, line in enumerate(r.text.split('\n')):
            if idx < 5:
                continue

            if line[0] == '#':
                if 'EXTINF' in line:
                    t['duration'] = float(line.split(':')[1][:-1])
                elif line == '#EXT-X-ENDLIST':
                    break
                else:
                    continue
            else:
                t['url'] = self._part_url(line)
                res.append(t)
                t = {}
            
        return res
    
    def _get_info(self, playable_url: str) -> Dict[str, Any]:
        try:
            cap = cv2.VideoCapture(playable_url)
            ret, frame = cap.read()
            if not ret:
                raise Exception("Failed to retreive video information! Unable to get frame.")
            
            fps = cap.get(cv2.CAP_PROP_FPS)
            res = frame.shape[:2] # h, w

            return {
                'fps': int(fps),
                'resolution': res,
                'p': res[0]
            }

        except Exception as e:
            raise Exception("Failed to retreive video information!") from e
        finally:
            if cap.isOpened():
                cap.release()

    
    def start(self, output_path: str = './m3u8.mp4', fourcc: str = 'mp4v'):
        if os.path.exists(output_path):
            raise Exception(f"File already exists for given output path!\n{output_path}")
        os.makedirs(output_path.replace(os.path.basename(output_path), ''), exist_ok=True)

        m3u8 = self._read_m3u8()
        info = self._get_info(m3u8[0]['url']) # use first part to get video information
        print(f"Found video stream at {info['fps']} with resolution of {info['p']}p")

        try:
            fourcc = cv2.VideoWriter_fourcc(*fourcc)
            writer = cv2.VideoWriter(output_path, fourcc, info['fps'], info['resolution'])

            readers: List[Tuple[PartReader, Queue]] = []

            print("Starting download...")
            loop = tqdm(range(0, len(m3u8), self.threads), total=len(m3u8))
            for idx in loop:
                for i in range(idx, idx+self.threads):
                    sub = m3u8[idx+i]
                    queue = Queue()
                    pr = PartReader(sub['url'], queue)
                    pr.start()

                    readers.append((pr, queue))
                
                for i in range(idx, idx+self.threads):
                    pr, queue = readers[i]
                    pr.join()

                    min_time = 1.0 / info['fps']

                    while True:
                        try:
                            start = time.time()

                            frame = queue.get(block=False)
                            writer.write(frame)
                            
                            if self.display:
                                cv2.imshow("Download", frame)
                                cv2.waitKey(1)

                            queue.task_done()

                            end = time.time()
                            took = end - start
                            if self.display and took < min_time:
                                time.sleep(min_time - took)

                        except Empty:
                            break

        except Exception as e:
            raise e
        
        finally:
            writer.release()
            cv2.destroyAllWindows()
    
        print("Done!")


if __name__ == "__main__":
    args = parser.parse_args()
    downloader = M3U8Downloader(args.url, args.threads, args.view)
    downloader.start(args.out, args.fourcc)