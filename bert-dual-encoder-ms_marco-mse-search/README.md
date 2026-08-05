---
tags:
- sentence-transformers
- sentence-similarity
- feature-extraction
- generated_from_trainer
- dataset_size:502931
- loss:MultipleNegativesRankingLoss
base_model: google-bert/bert-base-uncased
pipeline_tag: sentence-similarity
library_name: sentence-transformers
---

# SentenceTransformer based on google-bert/bert-base-uncased

This is a [sentence-transformers](https://www.SBERT.net) model finetuned from [google-bert/bert-base-uncased](https://huggingface.co/google-bert/bert-base-uncased) on the msmarco-bm25 dataset. It maps sentences & paragraphs to a 768-dimensional dense vector space and can be used for retrieval.

## Model Details

### Model Description
- **Model Type:** Sentence Transformer
- **Base model:** [google-bert/bert-base-uncased](https://huggingface.co/google-bert/bert-base-uncased) <!-- at revision 86b5e0934494bd15c9632b12f734a8a67f723594 -->
- **Maximum Sequence Length:** 512 tokens
- **Output Dimensionality:** 768 dimensions
- **Similarity Function:** Cosine Similarity
- **Supported Modality:** Text
- **Training Dataset:**
    - msmarco-bm25
<!-- - **Language:** Unknown -->
<!-- - **License:** Unknown -->

### Model Sources

- **Documentation:** [Sentence Transformers Documentation](https://sbert.net)
- **Repository:** [Sentence Transformers on GitHub](https://github.com/huggingface/sentence-transformers)
- **Hugging Face:** [Sentence Transformers on Hugging Face](https://huggingface.co/models?library=sentence-transformers)

### Full Model Architecture

```
SentenceTransformer(
  (0): Transformer({'transformer_task': 'feature-extraction', 'modality_config': {'text': {'method': 'forward', 'method_output_name': 'last_hidden_state'}}, 'module_output_name': 'token_embeddings', 'architecture': 'BertModel'})
  (1): Pooling({'embedding_dimension': 768, 'pooling_mode': 'mean', 'include_prompt': True})
)
```

## Usage

### Direct Usage (Sentence Transformers)

First install the Sentence Transformers library:

```bash
pip install -U sentence-transformers
```
Then you can load this model and run inference.
```python
from sentence_transformers import SentenceTransformer

# Download from the 🤗 Hub
model = SentenceTransformer("sentence_transformers_model_id")
# Run inference
sentences = [
    'The weather is lovely today.',
    "It's so sunny outside!",
    'He drove to the stadium.',
]
embeddings = model.encode(sentences)
print(embeddings.shape)
# [3, 768]

# Get the similarity scores for the embeddings
similarities = model.similarity(embeddings, embeddings)
print(similarities)
# tensor([[1.0000, 0.7568, 0.1821],
#         [0.7568, 1.0000, 0.1857],
#         [0.1821, 0.1857, 1.0000]])
```
<!--
### Direct Usage (Transformers)

<details><summary>Click to see the direct usage in Transformers</summary>

</details>
-->

<!--
### Downstream Usage (Sentence Transformers)

You can finetune this model on your own dataset.

<details><summary>Click to expand</summary>

</details>
-->

<!--
### Out-of-Scope Use

*List how the model may foreseeably be misused and address what users ought not to do with the model.*
-->

<!--
## Bias, Risks and Limitations

*What are the known or foreseeable issues stemming from this model? You could also flag here known failure cases or weaknesses of the model.*
-->

<!--
### Recommendations

*What are recommendations with respect to the foreseeable issues? For example, filtering explicit content.*
-->

## Training Details

### Training Dataset

#### msmarco-bm25

* Dataset: msmarco-bm25
* Size: 502,931 training samples
* Columns: <code>anchor</code>, <code>positive</code>, and <code>negative</code>
* Loss: [<code>MultipleNegativesRankingLoss</code>](https://sbert.net/docs/package_reference/sentence_transformer/losses.html#multiplenegativesrankingloss) with these parameters:
  ```json
  {
      "scale": 20.0,
      "similarity_fct": "cos_sim",
      "gather_across_devices": false,
      "directions": [
          "query_to_doc"
      ],
      "partition_mode": "joint",
      "hardness_mode": null,
      "hardness_strength": 0.0
  }
  ```

### Training Hyperparameters
#### Non-Default Hyperparameters

- `per_device_train_batch_size`: 64
- `max_steps`: 10000
- `learning_rate`: 2e-05
- `warmup_steps`: 0.1
- `fp16`: True
- `gradient_checkpointing`: True

#### All Hyperparameters
<details><summary>Click to expand</summary>

- `per_device_train_batch_size`: 64
- `num_train_epochs`: 3.0
- `max_steps`: 10000
- `learning_rate`: 2e-05
- `lr_scheduler_type`: linear
- `lr_scheduler_kwargs`: None
- `warmup_steps`: 0.1
- `optim`: adamw_torch_fused
- `optim_args`: None
- `weight_decay`: 0.0
- `adam_beta1`: 0.9
- `adam_beta2`: 0.999
- `adam_epsilon`: 1e-08
- `optim_target_modules`: None
- `gradient_accumulation_steps`: 1
- `average_tokens_across_devices`: True
- `max_grad_norm`: 1.0
- `label_smoothing_factor`: 0.0
- `bf16`: False
- `fp16`: True
- `bf16_full_eval`: False
- `fp16_full_eval`: False
- `tf32`: None
- `gradient_checkpointing`: True
- `gradient_checkpointing_kwargs`: None
- `torch_compile`: False
- `torch_compile_backend`: None
- `torch_compile_mode`: None
- `use_liger_kernel`: False
- `liger_kernel_config`: None
- `use_cache`: False
- `neftune_noise_alpha`: None
- `torch_empty_cache_steps`: None
- `auto_find_batch_size`: False
- `log_on_each_node`: True
- `logging_nan_inf_filter`: True
- `include_num_input_tokens_seen`: no
- `log_level`: passive
- `log_level_replica`: warning
- `disable_tqdm`: False
- `project`: huggingface
- `trackio_space_id`: None
- `trackio_bucket_id`: None
- `trackio_static_space_id`: None
- `per_device_eval_batch_size`: 8
- `prediction_loss_only`: True
- `eval_on_start`: False
- `eval_do_concat_batches`: True
- `eval_use_gather_object`: False
- `eval_accumulation_steps`: None
- `include_for_metrics`: []
- `batch_eval_metrics`: False
- `save_only_model`: False
- `save_on_each_node`: False
- `enable_jit_checkpoint`: False
- `push_to_hub`: False
- `hub_private_repo`: None
- `hub_model_id`: None
- `hub_strategy`: every_save
- `hub_always_push`: False
- `hub_revision`: None
- `load_best_model_at_end`: False
- `ignore_data_skip`: False
- `restore_callback_states_from_checkpoint`: False
- `full_determinism`: False
- `seed`: 42
- `data_seed`: None
- `use_cpu`: False
- `accelerator_config`: {'split_batches': False, 'dispatch_batches': None, 'even_batches': True, 'use_seedable_sampler': True, 'non_blocking': False, 'gradient_accumulation_kwargs': None}
- `parallelism_config`: None
- `dataloader_drop_last`: False
- `dataloader_num_workers`: 0
- `dataloader_pin_memory`: True
- `dataloader_persistent_workers`: False
- `dataloader_prefetch_factor`: None
- `remove_unused_columns`: True
- `label_names`: None
- `train_sampling_strategy`: random
- `length_column_name`: length
- `ddp_find_unused_parameters`: None
- `ddp_bucket_cap_mb`: None
- `ddp_broadcast_buffers`: False
- `ddp_static_graph`: None
- `ddp_backend`: None
- `ddp_timeout`: 1800
- `fsdp`: None
- `fsdp_config`: None
- `deepspeed`: None
- `debug`: []
- `skip_memory_metrics`: True
- `do_predict`: False
- `resume_from_checkpoint`: None
- `warmup_ratio`: None
- `local_rank`: -1
- `prompts`: None
- `batch_sampler`: batch_sampler
- `multi_dataset_batch_sampler`: proportional
- `router_mapping`: {}
- `learning_rate_mapping`: {}

</details>

### Training Logs
| Epoch  | Step  | Training Loss |
|:------:|:-----:|:-------------:|
| 0.01   | 100   | 2.4492        |
| 0.02   | 200   | 1.4631        |
| 0.03   | 300   | 1.0827        |
| 0.04   | 400   | 0.8492        |
| 0.05   | 500   | 0.6988        |
| 0.06   | 600   | 0.6573        |
| 0.07   | 700   | 0.6203        |
| 0.08   | 800   | 0.6072        |
| 0.09   | 900   | 0.5538        |
| 0.1    | 1000  | 0.5449        |
| 0.11   | 1100  | 0.5406        |
| 0.12   | 1200  | 0.5279        |
| 0.13   | 1300  | 0.5077        |
| 0.14   | 1400  | 0.5057        |
| 0.15   | 1500  | 0.4863        |
| 0.16   | 1600  | 0.4676        |
| 0.17   | 1700  | 0.4806        |
| 0.18   | 1800  | 0.4639        |
| 0.19   | 1900  | 0.4592        |
| 0.2    | 2000  | 0.4611        |
| 0.21   | 2100  | 0.4564        |
| 0.22   | 2200  | 0.4676        |
| 0.23   | 2300  | 0.4502        |
| 0.24   | 2400  | 0.4508        |
| 0.25   | 2500  | 0.4593        |
| 0.26   | 2600  | 0.4523        |
| 0.27   | 2700  | 0.4334        |
| 0.28   | 2800  | 0.4345        |
| 0.29   | 2900  | 0.4200        |
| 0.3    | 3000  | 0.4374        |
| 0.31   | 3100  | 0.4345        |
| 0.32   | 3200  | 0.4200        |
| 0.33   | 3300  | 0.4407        |
| 0.34   | 3400  | 0.4205        |
| 0.35   | 3500  | 0.4301        |
| 0.36   | 3600  | 0.4309        |
| 0.37   | 3700  | 0.4200        |
| 0.38   | 3800  | 0.4318        |
| 0.39   | 3900  | 0.4240        |
| 0.4    | 4000  | 0.4057        |
| 0.41   | 4100  | 0.4077        |
| 0.42   | 4200  | 0.4024        |
| 0.43   | 4300  | 0.4148        |
| 0.44   | 4400  | 0.4011        |
| 0.45   | 4500  | 0.4257        |
| 0.46   | 4600  | 0.3892        |
| 0.47   | 4700  | 0.4132        |
| 0.48   | 4800  | 0.4133        |
| 0.49   | 4900  | 0.3964        |
| 0.5    | 5000  | 0.4036        |
| 0.51   | 5100  | 0.4057        |
| 0.52   | 5200  | 0.3911        |
| 0.53   | 5300  | 0.4060        |
| 0.54   | 5400  | 0.4157        |
| 0.55   | 5500  | 0.3818        |
| 0.56   | 5600  | 0.3889        |
| 0.57   | 5700  | 0.3867        |
| 0.58   | 5800  | 0.4182        |
| 0.59   | 5900  | 0.4028        |
| 0.6    | 6000  | 0.3911        |
| 0.61   | 6100  | 0.3760        |
| 0.62   | 6200  | 0.4032        |
| 0.63   | 6300  | 0.3809        |
| 0.64   | 6400  | 0.3876        |
| 0.65   | 6500  | 0.3840        |
| 0.66   | 6600  | 0.3746        |
| 0.67   | 6700  | 0.3806        |
| 0.68   | 6800  | 0.3957        |
| 0.69   | 6900  | 0.3674        |
| 0.7    | 7000  | 0.3774        |
| 0.71   | 7100  | 0.3878        |
| 0.72   | 7200  | 0.3753        |
| 0.73   | 7300  | 0.3715        |
| 0.74   | 7400  | 0.3829        |
| 0.75   | 7500  | 0.3873        |
| 0.76   | 7600  | 0.3757        |
| 0.77   | 7700  | 0.3612        |
| 0.78   | 7800  | 0.3789        |
| 1.0041 | 7900  | 0.3572        |
| 1.0141 | 8000  | 0.3802        |
| 1.0241 | 8100  | 0.3749        |
| 1.0341 | 8200  | 0.3718        |
| 1.0441 | 8300  | 0.3427        |
| 1.0541 | 8400  | 0.3463        |
| 1.0641 | 8500  | 0.3380        |
| 1.0741 | 8600  | 0.3221        |
| 1.0841 | 8700  | 0.3152        |
| 1.0941 | 8800  | 0.2838        |
| 1.1041 | 8900  | 0.2858        |
| 1.1141 | 9000  | 0.2831        |
| 1.1241 | 9100  | 0.2751        |
| 1.1341 | 9200  | 0.2795        |
| 1.1441 | 9300  | 0.2782        |
| 1.1541 | 9400  | 0.2686        |
| 1.1641 | 9500  | 0.2651        |
| 1.1741 | 9600  | 0.2632        |
| 1.1841 | 9700  | 0.2656        |
| 1.1941 | 9800  | 0.2623        |
| 1.2041 | 9900  | 0.2657        |
| 1.2141 | 10000 | 0.2699        |


### Training Time
- **Training**: 4.6 hours

### Framework Versions
- Python: 3.14.6
- Sentence Transformers: 5.6.1
- Transformers: 5.14.1
- PyTorch: 2.9.1+rocm6.4
- Accelerate: 1.14.0
- Datasets: 5.0.1
- Tokenizers: 0.22.2

## Citation

### BibTeX

#### Sentence Transformers
```bibtex
@inproceedings{reimers-2019-sentence-bert,
    title = "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks",
    author = "Reimers, Nils and Gurevych, Iryna",
    booktitle = "Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing",
    month = "11",
    year = "2019",
    publisher = "Association for Computational Linguistics",
    url = "https://arxiv.org/abs/1908.10084",
}
```

#### MultipleNegativesRankingLoss
```bibtex
@misc{oord2019representationlearningcontrastivepredictive,
      title={Representation Learning with Contrastive Predictive Coding},
      author={Aaron van den Oord and Yazhe Li and Oriol Vinyals},
      year={2019},
      eprint={1807.03748},
      archivePrefix={arXiv},
      primaryClass={cs.LG},
      url={https://arxiv.org/abs/1807.03748},
}
```


## Glossary

This was specifically trained for a project in the MSE course at the university of Tübingen.


## Model Card Authors
Nico Henzler, Lukas Henzler, Samuel Scheer

