#!/usr/bin/env python
# -*- coding: UTF-8 -*-


import re
import nltk
import torch
from tqdm import tqdm
from collections import Counter
from bert_serving.client import BertClient



PAD="[PAD]"
UNK="[UNK]"
BOS="[BOS]"
EOS="[EOS]"
NUM="[NUM]"

def tokenize(s):
    """
    tokenize
    """
    s = re.sub('\d+', NUM, s).lower()
    # tokens = nltk.RegexpTokenizer(r'\w+|<sil>|[^\w\s]+').tokenize(s)
    tokens = s.split(' ')
    return tokens


class Field(object):

    def __init__(self,
                 sequential=False,
                 dtype=None):
        self.sequential = sequential
        self.dtype = dtype if dtype is not None else int

    def str2num(self, string):

        raise NotImplementedError

    def num2str(self, number):

        raise NotImplementedError

    def numericalize(self, strings):

        if isinstance(strings, str):
            return self.str2num(strings)
        else:
            return [self.numericalize(s) for s in strings]

    def denumericalize(self, numbers):

        if isinstance(numbers, torch.Tensor):
            with torch.cuda.device_of(numbers):
                numbers = numbers.tolist()
        if self.sequential:
            if not isinstance(numbers[0], list):
                return self.num2str(numbers)
            else:
                return [self.denumericalize(x) for x in numbers]
        else:
            if not isinstance(numbers, list):
                return self.num2str(numbers)
            else:
                return [self.denumericalize(x) for x in numbers]


class NumberField(Field):

    def __init__(self,
                 sequential=False,
                 dtype=None):
        super(NumberField, self).__init__(sequential=sequential,
                                          dtype=dtype)

    def str2num(self, string):

        if self.sequential:
            return [self.dtype(s) for s in string.split(" ")]
        else:
            return self.dtype(string)

    def num2str(self, number):

        if self.sequential:
            return " ".join([str(x) for x in number])
        else:
            return str(number)


class TextField(Field):

    def __init__(self,
                 tokenize_fn=None,
                 pad_token=PAD,
                 unk_token=UNK,
                 bos_token=BOS,
                 eos_token=EOS,
                 special_tokens=None,
                 embed_file=None):
        super(TextField, self).__init__(sequential=True,
                                        dtype=int)
        self.tokenize_fn = tokenize_fn if tokenize_fn is not None else str.split
        self.pad_token = pad_token
        self.unk_token = unk_token
        self.bos_token = bos_token
        self.eos_token = eos_token
        self.embed_file = embed_file

        specials = [self.pad_token, self.unk_token,
                    self.bos_token, self.eos_token]
        self.specials = [x for x in specials if x is not None]

        if special_tokens is not None:
            for token in special_tokens:
                if token not in self.specials:
                    self.specials.append(token)

        self.itos = []
        self.stoi = {}
        self.vocab_size = 0
        self.embeddings = None

    def build_vocab(self, texts, min_freq=0, max_size=None):

        def flatten(xs):

            flat_xs = []
            for x in xs:
                if isinstance(x, str):
                    flat_xs.append(x)
                elif isinstance(x[0], str):
                    flat_xs += x
                else:
                    flat_xs += flatten(x)
            return flat_xs

        # flatten texts
        texts = flatten(texts)

        counter = Counter()
        for string in tqdm(texts):
            tokens = self.tokenize_fn(string)
            counter.update(tokens)

        # frequencies of special tokens are not counted when building vocabulary
        # in frequency order
        for tok in self.specials:
            del counter[tok]

        self.itos = list(self.specials)

        if max_size is not None:
            max_size = max_size + len(self.itos)

        # sort by frequency, then alphabetically
        words_and_frequencies = sorted(counter.items(), key=lambda tup: tup[0])
        words_and_frequencies.sort(key=lambda tup: tup[1], reverse=True)

        cover = 0
        for word, freq in words_and_frequencies:
            if word=='' or word=='\u3000':
                print(f'跳过{word}')
                continue
            if freq < min_freq or len(self.itos) == max_size:
                break
            self.itos.append(word)
            cover += freq
        cover = cover / sum(freq for _, freq in words_and_frequencies)
        print(
            "Built vocabulary of size {} (coverage: {:.3f})".format(len(self.itos), cover))

        self.stoi = {tok: i for i, tok in enumerate(self.itos)}
        self.vocab_size = len(self.itos)

        #if self.embed_file is not None:
        self.embeddings = self.build_word_embeddings(self.embed_file)

    def build_word_embeddings(self, embed_file):
        bc = BertClient(ip='34.84.105.174')
        try:
            embeds=bc.encode(self.itos).tolist()
            print('buillding embedding succeed')
        except:
            raise('building embedding fail')
       
        return embeds

    def dump_vocab(self):

        vocab = {"itos": self.itos,
                 "embeddings": self.embeddings}
        return vocab

    def load_vocab(self, vocab):

        self.itos = vocab["itos"]
        self.stoi = {tok: i for i, tok in enumerate(self.itos)}
        self.vocab_size = len(self.itos)
        self.embeddings = vocab["embeddings"]

    def str2num(self, string):

        tokens = []
        unk_idx = self.stoi[self.unk_token]

        if self.bos_token:
            tokens.append(self.bos_token)

        tokens += self.tokenize_fn(string)

        if self.eos_token:
            tokens.append(self.eos_token)
        indices = [self.stoi.get(tok, unk_idx) for tok in tokens]
        return indices

    def num2str(self, number):

        tokens = [self.itos[x] for x in number]
        if tokens[0] == self.bos_token:
            tokens = tokens[1:]
        text = []
        for w in tokens:
            if w != self.eos_token:
                text.append(w)
            else:
                break
        text = [w for w in text if w not in (self.pad_token, )]
        text = " ".join(text)
        return text
