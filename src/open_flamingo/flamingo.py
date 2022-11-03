'''
Main Flamingo class
Uses gated cross attention with Perceiver resampler
'''

from typing import List

import torch
from torch import nn
from transformers import MaxLengthCriteria

from .flamingo_lm import OPTForCausalLMFlamingo
from .helpers import GatedCrossAttentionBlock, PerceiverResampler


class Flamingo(nn.Module):
    def __init__(self, vision_encoder: nn.Module, lang_encoder: OPTForCausalLMFlamingo):
        """
        Args:
            vision_encoder (nn.Module): Any vision encoder
            lang_encoder (OPTForCausalLMFlamingo): An instance of OPTForCausalLMFlamingo
        """
        super().__init__()
        self.vision_encoder = vision_encoder
        self.lang_encoder = lang_encoder
        self.lang_encoder.init_flamingo()

    def forward(self, vision_x: torch.Tensor, lang_x: torch.Tensor, attention_mask: torch.Tensor = None, labels: torch.Tensor = None):
        vision_attended = self.vision_encoder(vision_x)
        output = self.lang_encoder(vision_attended.last_hidden_state, lang_x, attention_mask=attention_mask, labels=labels)
        
        self.lang_encoder.clear_conditioned_layers()
        return output

    def generate(self, vision_x: torch.Tensor, lang_x: torch.Tensor, max_length: int, eoc_token_id: int, attention_mask: torch.Tensor = None, num_beams=1, temperature=1.0, top_k=0, top_p=1.0, no_repeat_ngram_size=0, length_penalty=1.0, num_return_sequences=1, do_sample=False, early_stopping=False):
        """ Adapted from https://github.com/huggingface/transformers/blob/v4.23.1/src/transformers/generation_utils.py#L1637
        This is a barebones implementation of greedy decoding. We should work on better methods later.

        Args:
            vision_x (torch.Tensor): Vision input
            lang_x (torch.Tensor): Language input
            max_length (int): Maximum length of the output
            eoc_token_id (int): End of chunk token id
            attention_mask (torch.Tensor, optional): Attention mask. Defaults to None.
            num_beams (int, optional): Number of beams. Defaults to 1.
            temperature (float, optional): Temperature. Defaults to 1.0.
            top_k (int, optional): Top k. Defaults to 0.
            top_p (float, optional): Top p. Defaults to 1.0.
            no_repeat_ngram_size (int, optional): No repeat ngram size. Defaults to 0.
            length_penalty (float, optional): Length penalty. Defaults to 1.0.
            num_return_sequences (int, optional): Number of return sequences. Defaults to 1.
            do_sample (bool, optional): Do sample. Defaults to False.
            early_stopping (bool, optional): Early stopping. Defaults to False.
        Returns:
            torch.Tensor: lang_x with generated tokens appended to it
        """

        vision_attended = self.vision_encoder(vision_x).last_hidden_state
        vision_attended = self.lang_encoder.perceiver_resampler(
            vision_attended)

        # condition on vis_attended
        for layer in self.lang_encoder.model.decoder.layers:
            layer.condition(vision_attended)

        output = self.lang_encoder.generate(
            lang_x,
            attention_mask=attention_mask,
            max_length=max_length,
            eos_token_id=eoc_token_id,
            num_beams=num_beams,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            no_repeat_ngram_size=no_repeat_ngram_size,
            length_penalty=length_penalty,
            num_return_sequences=num_return_sequences,
            do_sample=do_sample,
            early_stopping=early_stopping
        )
        
        self.lang_encoder.clear_conditioned_layers()
        return output
