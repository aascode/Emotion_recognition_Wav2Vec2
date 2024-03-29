# -*- coding: utf-8 -*-
"""Emotion recognition using Wav2Vec2

Original file is located at
    https://colab.research.google.com/github/m3hrdadfi/soxan/blob/main/notebooks/Emotion_recognition_in_Greek_speech_using_Wav2Vec2.ipynb

**Wav2Vec 2.0** is a pretrained model for Automatic Speech Recognition (ASR) and was released in [September 2020](https://ai.facebook.com/blog/wav2vec-20-learning-the-structure-of-speech-from-raw-audio/) by Alexei Baevski, Michael Auli, and Alex Conneau.  Soon after the superior performance of Wav2Vec2 was demonstrated on the English ASR dataset LibriSpeech, *Facebook AI* presented XLSR-Wav2Vec2 (click [here](https://arxiv.org/abs/2006.13979)). XLSR stands for *cross-lingual  speech representations* and refers to XLSR-Wav2Vec2`s ability to learn speech representations that are useful across multiple languages.

Similar to Wav2Vec2, XLSR-Wav2Vec2 learns powerful speech representations from hundreds of thousands of hours of speech in more than 50 languages of unlabeled speech. Similar, to [BERT's masked language modeling](http://jalammar.github.io/illustrated-bert/), the model learns contextualized speech representations by randomly masking feature vectors before passing them to a transformer network.

![wav2vec2_structure](https://raw.githubusercontent.com/patrickvonplaten/scientific_images/master/xlsr_wav2vec2.png)

The authors show for the first time that massively pretraining an ASR model on cross-lingual unlabeled speech data, followed by language-specific fine-tuning on very little labeled data achieves state-of-the-art results. See Table 1-5 of the official [paper](https://arxiv.org/pdf/2006.13979.pdf).

During fine-tuning week hosted by HuggingFace, more than 300 people participated in tuning XLSR-Wav2Vec2's pretrained on low-resources ASR dataset for more than 50 languages. This model is fine-tuned using [Connectionist Temporal Classification](https://distill.pub/2017/ctc/) (CTC), an algorithm used to train neural networks for sequence-to-sequence problems and mainly in Automatic Speech Recognition and handwriting recognition. Follow this [notebook](https://colab.research.google.com/github/patrickvonplaten/notebooks/blob/master/Fine_Tune_XLSR_Wav2Vec2_on_Turkish_ASR_with_%F0%9F%A4%97_Transformers.ipynb#scrollTo=Gx9OdDYrCtQ1) for more information about XLSR-Wav2Vec2 fine-tuning.

This model was shown significant results in many low-resources languages. You can see the [competition board](https://paperswithcode.com/dataset/common-voice) or even testing the models from the [HuggingFace hub](https://huggingface.co/models?filter=xlsr-fine-tuning-week).

"""
import os

# prepare dataset
if __name__ == '__main__' and not (os.path.exists("./content/data/train.csv") and os.path.exists("./content/data/train.csv")):
    import prepare_data_paths

"""## Prepare Data for Training"""

# Loading the created dataset using datasets
from datasets import load_dataset, load_metric, Dataset

data_files = {
    "train": "./content/data/train.csv",
    "validation": "./content/data/test.csv",
}

dataset = load_dataset("csv", data_files=data_files, delimiter="\t", )
train_dataset = dataset["train"]
eval_dataset = dataset["validation"]

print('train_dataset: ', train_dataset)
print('eval_dataset: ', eval_dataset)

# We need to specify the input and output column
input_column = "path"
output_column = "emotion"

# we need to distinguish the unique labels in our SER dataset
label_list = train_dataset.unique(output_column)
label_list.sort()  # Let's sort it for determinism
num_labels = len(label_list)
print(f"A classification problem with {num_labels} classes: {label_list}")

"""In order to preprocess the audio into our classification model, we need to set up the relevant Wav2Vec2 assets regarding our language in this case `lighteternal/wav2vec2-large-xlsr-53-greek` fine-tuned by [Dimitris Papadopoulos](https://huggingface.co/lighteternal/wav2vec2-large-xlsr-53-greek). To handle the context representations in any audio length we use a merge strategy plan (pooling mode) to concatenate that 3D representations into 2D representations.

There are three merge strategies `mean`, `sum`, and `max`. In this example, we achieved better results on the mean approach. In the following, we need to initiate the config and the feature extractor from the Dimitris model.
"""

from transformers import AutoConfig, Wav2Vec2Processor

model_name_or_path = "lighteternal/wav2vec2-large-xlsr-53-greek"
pooling_mode = "mean"

# config
config = AutoConfig.from_pretrained(
    model_name_or_path,
    num_labels=num_labels,
    label2id={label: i for i, label in enumerate(label_list)},
    id2label={i: label for i, label in enumerate(label_list)},
    finetuning_task="wav2vec2_clf",
)
setattr(config, 'pooling_mode', pooling_mode)

processor = Wav2Vec2Processor.from_pretrained(model_name_or_path,)
target_sampling_rate = processor.feature_extractor.sampling_rate
print(f"The target sampling rate: {target_sampling_rate}")

"""# Preprocess Data

So far, we downloaded, loaded, and split the SER dataset into train and test sets. The instantiated our strategy configuration for using context representations in our classification problem SER. Now, we need to extract features from the audio path in context representation tensors and feed them into our classification model to determine the emotion in the speech.

Since the audio file is saved in the `.wav` format, it is easy to use **[Librosa](https://librosa.org/doc/latest/index.html)** or others, but we suppose that the format may be in the `.mp3` format in case of generality. We found that the **[Torchaudio](https://pytorch.org/audio/stable/index.html)** library works best for reading in `.mp3` data.

An audio file usually stores both its values and the sampling rate with which the speech signal was digitalized. We want to store both in the dataset and write a **map(...)** function accordingly. Also, we need to handle the string labels into integers for our specific classification task in this case, the **single-label classification** you may want to use for your **regression** or even **multi-label classification**.
"""
import torchaudio
import numpy as np
from tqdm import tqdm
from datasets import concatenate_datasets
from nested_array_catcher import nested_array_catcher

def speech_file_to_array_fn(path):
    speech_array, sampling_rate = torchaudio.load(path)
    resampler = torchaudio.transforms.Resample(sampling_rate, target_sampling_rate)
    speech = resampler(speech_array).squeeze().numpy() #  <class 'numpy.ndarray'>
    return speech

def label_to_id(label, label_list):
    if len(label_list) > 0:
        return label_list.index(label) if label in label_list else -1
    return label

def preprocess_function(examples):
    speech_list = [speech_file_to_array_fn(path) for path in examples[input_column]]
    target_list = [label_to_id(label, label_list) for label in examples[output_column]]

    result = processor(speech_list, sampling_rate=target_sampling_rate) # <class 'transformers.feature_extraction_utils.BatchFeature'> , padding=True??
    result["labels"] = list(target_list) # list of indicies of of target label

    for i in range(len(result['input_values'])):
        result['input_values'][i] = nested_array_catcher(result['input_values'][i])
        # for j in range(len(result['input_values'][i])):
        #     try:
        #         assert isinstance(result['input_values'][i][j], np.float32)
        #     except Exception as e:
        #         # print(e)
        #         print(i, j) # 2791 0, 2791 1, 5097 0, 5097 1
        #         print(294, type(result['input_values'][i]), type(result['input_values'][i][j])) # <class 'numpy.ndarray'> <class 'numpy.ndarray'>
        #         result['input_values'][i] = result['input_values'][i][j]
        #         print('new type: ', type(result['input_values'][i][j]), result['input_values'][i][j], result['input_values'][i])

    return result

# train_dataset = train_dataset.map(
#     preprocess_function,
#     batch_size=1000, # 9729
#     batched=True,
#     num_proc=4 ##
# )
# eval_dataset = eval_dataset.map(
#     preprocess_function,
#     batch_size=100, #100
#     batched=True,
#     num_proc=4
# )
#
# np.save('./features/speech_list_eval_.npy', eval_dataset['input_values'], allow_pickle=True)
# print(f"eval features saved to ./features/speech_list_eval_.npy")
# exit() # slurm-36065.out

def ppf(examples, split): # A single process preprocess_function
    filepath = f'./features/speech_list_{split}.npy'
    if os.path.exists(filepath):
        with open(filepath, 'rb') as f:
            speech_list = np.load(f, allow_pickle=True)
        print('\nLOADED FEATURES FROM FILE')
        speech_list = list(speech_list)
    else:
        print('\nPROCESSING')
        speech_list = [speech_file_to_array_fn(path) for path in tqdm(examples['path'])]
        # save to file
        np.save(filepath, speech_list, allow_pickle=True)
        print(f"\nFeatures saved to {filepath}")
    print('speech_list: ', len(speech_list))
    target_list = [label_to_id(label, label_list) for label in examples['emotion']]

    result = processor(speech_list, sampling_rate=target_sampling_rate) # <class 'transformers.feature_extraction_utils.BatchFeature'> , padding=True??
    result["labels"] = list(target_list) # list of indicies of of target label

    print('\nASSERTING dtype')
    for i in range(len(result['input_values'])):
        result['input_values'][i] = nested_array_catcher(result['input_values'][i])
        # for j in range(len(result['input_values'][i])):
        #     try:
        #         assert isinstance(result['input_values'][i][j], np.float32)
        #     except Exception as e:
        #         print(i, j) # 2791 0, 2791 1, 5097 0, 5097 1,
        #         result['input_values'][i] = result['input_values'][i][j]

    return result

train_dataset_pp = ppf(train_dataset, 'train')
train_dataset_pp = Dataset.from_dict(train_dataset_pp)
eval_dataset_pp = ppf(eval_dataset, 'eval')
eval_dataset_pp = Dataset.from_dict(eval_dataset_pp)

assert len(train_dataset) == len(train_dataset_pp)
assert len(eval_dataset) == len(eval_dataset_pp)
train_dataset = concatenate_datasets([train_dataset, train_dataset_pp],axis=1)
eval_dataset = concatenate_datasets([eval_dataset, eval_dataset_pp],axis=1)

print(train_dataset.features.type) # <class 'datasets.arrow_dataset.Dataset'> ### but we have <class 'transformers.feature_extraction_utils.BatchFeature'>
print(train_dataset)

idx = 0
# print(f"Training input_values: {train_dataset[idx]['input_values']}")
# print(f"Training attention_mask: {train_dataset[idx]['attention_mask']}")
print(f"Training labels: {train_dataset[idx]['labels']} - {train_dataset[idx]['emotion']}")

"""Great, now we've successfully read all the audio files, resampled the audio files to 16kHz, and mapped each audio to the corresponding label.

## Model

Before diving into the training part, we need to build our classification model based on the merge strategy.
"""

from dataclasses import dataclass
from typing import Optional, Tuple
import torch
from transformers.file_utils import ModelOutput


@dataclass
class SpeechClassifierOutput(ModelOutput):
    loss: Optional[torch.FloatTensor] = None
    logits: torch.FloatTensor = None
    hidden_states: Optional[Tuple[torch.FloatTensor]] = None
    attentions: Optional[Tuple[torch.FloatTensor]] = None

import torch
import torch.nn as nn
from torch.nn import BCEWithLogitsLoss, CrossEntropyLoss, MSELoss

from transformers.models.wav2vec2.modeling_wav2vec2 import (
    Wav2Vec2PreTrainedModel,
    Wav2Vec2Model
)


class Wav2Vec2ClassificationHead(nn.Module):
    """Head for wav2vec classification task."""

    def __init__(self, config):
        super().__init__()
        self.dense = nn.Linear(config.hidden_size, config.hidden_size)
        self.dropout = nn.Dropout(config.final_dropout)
        self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

    def forward(self, features, **kwargs):
        x = features
        x = self.dropout(x)
        x = self.dense(x)
        x = torch.tanh(x)
        x = self.dropout(x)
        x = self.out_proj(x)
        return x


class Wav2Vec2ForSpeechClassification(Wav2Vec2PreTrainedModel):
    def __init__(self, config):
        super().__init__(config)
        self.num_labels = config.num_labels
        self.pooling_mode = config.pooling_mode
        self.config = config

        self.wav2vec2 = Wav2Vec2Model(config)
        self.classifier = Wav2Vec2ClassificationHead(config)

        self.init_weights()

    def freeze_feature_extractor(self):
        self.wav2vec2.feature_extractor._freeze_parameters()

    def merged_strategy(
            self,
            hidden_states,
            mode="mean"
    ):
        if mode == "mean":
            outputs = torch.mean(hidden_states, dim=1)
        elif mode == "sum":
            outputs = torch.sum(hidden_states, dim=1)
        elif mode == "max":
            outputs = torch.max(hidden_states, dim=1)[0]
        else:
            raise Exception(
                "The pooling method hasn't been defined! Your pooling mode must be one of these ['mean', 'sum', 'max']")

        return outputs

    def forward(
            self,
            input_values,
            attention_mask=None,
            output_attentions=None,
            output_hidden_states=None,
            return_dict=None,
            labels=None,
    ):
        return_dict = return_dict if return_dict is not None else self.config.use_return_dict
        outputs = self.wav2vec2(
            input_values,
            attention_mask=attention_mask,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict,
        )
        hidden_states = outputs[0]
        hidden_states = self.merged_strategy(hidden_states, mode=self.pooling_mode)
        logits = self.classifier(hidden_states)

        loss = None
        if labels is not None:
            if self.config.problem_type is None:
                if self.num_labels == 1:
                    self.config.problem_type = "regression"
                elif self.num_labels > 1 and (labels.dtype == torch.long or labels.dtype == torch.int):
                    self.config.problem_type = "single_label_classification"
                else:
                    self.config.problem_type = "multi_label_classification"

            if self.config.problem_type == "regression":
                loss_fct = MSELoss()
                loss = loss_fct(logits.view(-1, self.num_labels), labels)
            elif self.config.problem_type == "single_label_classification":
                loss_fct = CrossEntropyLoss()
                loss = loss_fct(logits.view(-1, self.num_labels), labels.view(-1))
            elif self.config.problem_type == "multi_label_classification":
                loss_fct = BCEWithLogitsLoss()
                loss = loss_fct(logits, labels)

        if not return_dict:
            output = (logits,) + outputs[2:]
            return ((loss,) + output) if loss is not None else output

        return SpeechClassifierOutput(
            loss=loss,
            logits=logits,
            hidden_states=outputs.hidden_states,
            attentions=outputs.attentions,
        )

"""## Training

The data is processed so that we are ready to start setting up the training pipeline. We will make use of 🤗's [Trainer](https://huggingface.co/transformers/master/main_classes/trainer.html?highlight=trainer) for which we essentially need to do the following:

- Define a data collator. In contrast to most NLP models, XLSR-Wav2Vec2 has a much larger input length than output length. *E.g.*, a sample of input length 50000 has an output length of no more than 100. Given the large input sizes, it is much more efficient to pad the training batches dynamically meaning that all training samples should only be padded to the longest sample in their batch and not the overall longest sample. Therefore, fine-tuning XLSR-Wav2Vec2 requires a special padding data collator, which we will define below

- Evaluation metric. During training, the model should be evaluated on the word error rate. We should define a `compute_metrics` function accordingly

- Load a pretrained checkpoint. We need to load a pretrained checkpoint and configure it correctly for training.

- Define the training configuration.

After having fine-tuned the model, we will correctly evaluate it on the test data and verify that it has indeed learned to correctly transcribe speech.

### Set-up Trainer

Let's start by defining the data collator. The code for the data collator was copied from [this example](https://github.com/huggingface/transformers/blob/9a06b6b11bdfc42eea08fa91d0c737d1863c99e3/examples/research_projects/wav2vec2/run_asr.py#L81).

Without going into too many details, in contrast to the common data collators, this data collator treats the `input_values` and `labels` differently and thus applies to separate padding functions on them (again making use of XLSR-Wav2Vec2's context manager). This is necessary because in speech input and output are of different modalities meaning that they should not be treated by the same padding function.
Analogous to the common data collators, the padding tokens in the labels with `-100` so that those tokens are **not** taken into account when computing the loss.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Union
import torch

import transformers
from transformers import Wav2Vec2Processor


@dataclass
class DataCollatorCTCWithPadding:
    """
    Data collator that will dynamically pad the inputs received.
    Args:
        processor (:class:`~transformers.Wav2Vec2Processor`)
            The processor used for proccessing the data.
        padding (:obj:`bool`, :obj:`str` or :class:`~transformers.tokenization_utils_base.PaddingStrategy`, `optional`, defaults to :obj:`True`):
            Select a strategy to pad the returned sequences (according to the model's padding side and padding index)
            among:
            * :obj:`True` or :obj:`'longest'`: Pad to the longest sequence in the batch (or no padding if only a single
              sequence if provided).
            * :obj:`'max_length'`: Pad to a maximum length specified with the argument :obj:`max_length` or to the
              maximum acceptable input length for the model if that argument is not provided.
            * :obj:`False` or :obj:`'do_not_pad'` (default): No padding (i.e., can output a batch with sequences of
              different lengths).
        max_length (:obj:`int`, `optional`):
            Maximum length of the ``input_values`` of the returned list and optionally padding length (see above).
        max_length_labels (:obj:`int`, `optional`):
            Maximum length of the ``labels`` returned list and optionally padding length (see above).
        pad_to_multiple_of (:obj:`int`, `optional`):
            If set will pad the sequence to a multiple of the provided value.
            This is especially useful to enable the use of Tensor Cores on NVIDIA hardware with compute capability >=
            7.5 (Volta).
    """

    processor: Wav2Vec2Processor
    padding: Union[bool, str] = True
    max_length: Optional[int] = None
    max_length_labels: Optional[int] = None
    pad_to_multiple_of: Optional[int] = None
    pad_to_multiple_of_labels: Optional[int] = None

    def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]) -> Dict[str, torch.Tensor]:
        input_features = [{"input_values": feature["input_values"]} for feature in features]
        label_features = [feature["labels"] for feature in features]

        d_type = torch.long if isinstance(label_features[0], int) else torch.float

        batch = self.processor.pad(
            input_features,
            padding=self.padding,
            max_length=self.max_length,
            pad_to_multiple_of=self.pad_to_multiple_of,
            return_tensors="pt",
        )

        batch["labels"] = torch.tensor(label_features, dtype=d_type)

        return batch

data_collator = DataCollatorCTCWithPadding(processor=processor, padding=True)

"""Next, the evaluation metric is defined. There are many pre-defined metrics for classification/regression problems, but in this case, we would continue with just **Accuracy** for classification and **MSE** for regression. You can define other metrics on your own."""

is_regression = False

import numpy as np
from transformers import EvalPrediction

# print(599)
def compute_metrics(p: EvalPrediction):
    preds = p.predictions[0] if isinstance(p.predictions, tuple) else p.predictions
    preds = np.squeeze(preds) if is_regression else np.argmax(preds, axis=1)

    if is_regression:
        return {"mse": ((preds - p.label_ids) ** 2).mean().item()}
    else:
        return {"accuracy": (preds == p.label_ids).astype(np.float32).mean().item()}

"""Now, we can load the pretrained XLSR-Wav2Vec2 checkpoint into our classification model with a pooling strategy."""

model = Wav2Vec2ForSpeechClassification.from_pretrained(
    model_name_or_path,
    config=config,
)

"""The first component of XLSR-Wav2Vec2 consists of a stack of CNN layers that are used to extract acoustically meaningful - but contextually independent - features from the raw speech signal. This part of the model has already been sufficiently trained during pretraining and as stated in the [paper](https://arxiv.org/pdf/2006.13979.pdf) does not need to be fine-tuned anymore.
Thus, we can set the `requires_grad` to `False` for all parameters of the *feature extraction* part.
"""

model.freeze_feature_extractor()

"""In a final step, we define all parameters related to training.
To give more explanation on some of the parameters:
- `learning_rate` and `weight_decay` were heuristically tuned until fine-tuning has become stable. Note that those parameters strongly depend on the Common Voice dataset and might be suboptimal for other speech datasets.

For more explanations on other parameters, one can take a look at the [docs](https://huggingface.co/transformers/master/main_classes/trainer.html?highlight=trainer#trainingarguments).

**Note**: If one wants to save the trained models in his/her google drive the commented-out `output_dir` can be used instead.
"""

# from google.colab import drive

# drive.mount('/gdrive')

from transformers import TrainingArguments

training_args = TrainingArguments(
    output_dir="./content/wav2vec2-xlsr-greek-speech-emotion-recognition",
    # output_dir="/content/gdrive/MyDrive/wav2vec2-xlsr-greek-speech-emotion-recognition"
    per_device_train_batch_size=4,
    per_device_eval_batch_size=4,
    gradient_accumulation_steps=2,
    evaluation_strategy="steps",
    num_train_epochs=1.0,
    fp16=True,
    save_steps=10,
    eval_steps=10,
    logging_steps=10,
    learning_rate=1e-4,
    save_total_limit=2,
)

"""For future use we can create our training script, we do it in a simple way. You can add more on you own."""

from typing import Any, Dict, Union

import torch
from packaging import version
from torch import nn

from transformers import (
    Trainer,
    is_apex_available,
)

if is_apex_available():
    from apex import amp

if version.parse(torch.__version__) >= version.parse("1.6"):
    _is_native_amp_available = True
    from torch.cuda.amp import autocast


class CTCTrainer(Trainer):
    def training_step(self, model: nn.Module, inputs: Dict[str, Union[torch.Tensor, Any]]) -> torch.Tensor:
        """
        Perform a training step on a batch of inputs.

        Subclass and override to inject custom behavior.

        Args:
            model (:obj:`nn.Module`):
                The model to train.
            inputs (:obj:`Dict[str, Union[torch.Tensor, Any]]`):
                The inputs and targets of the model.

                The dictionary will be unpacked before being fed to the model. Most models expect the targets under the
                argument :obj:`labels`. Check your model's documentation for all accepted arguments.

        Return:
            :obj:`torch.Tensor`: The tensor with training loss on this batch.
        """

        model.train()
        inputs = self._prepare_inputs(inputs)

        if self.use_amp:
            with autocast():
                loss = self.compute_loss(model, inputs)
        else:
            loss = self.compute_loss(model, inputs)

        if self.args.gradient_accumulation_steps > 1:
            loss = loss / self.args.gradient_accumulation_steps

        if self.use_amp:
            self.scaler.scale(loss).backward()
        elif self.use_apex:
            with amp.scale_loss(loss, self.optimizer) as scaled_loss:
                scaled_loss.backward()
        elif self.deepspeed:
            self.deepspeed.backward(loss)
        else:
            loss.backward()

        return loss.detach()

"""Now, all instances can be passed to Trainer and we are ready to start training!"""

trainer = CTCTrainer(
    model=model,
    data_collator=data_collator,
    args=training_args,
    compute_metrics=compute_metrics,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    tokenizer=processor.feature_extractor,
)

"""### Training

Training will take between 10 and 60 minutes depending on the GPU allocated to this notebook.

In case you want to use this google colab to fine-tune your model, you should make sure that your training doesn't stop due to inactivity. A simple hack to prevent this is to paste the following code into the console of this tab (right mouse click -> inspect -> Console tab and insert code).

```javascript
function ConnectButton(){
    console.log("Connect pushed");
    document.querySelector("#top-toolbar > colab-connect-button").shadowRoot.querySelector("#connect").click()
}
setInterval(ConnectButton,60000);
```
"""

trainer.train()

# Evaluation
import evaluation

# Prediction
# import prediction

# """The training loss goes down and we can see that the Acurracy on the test set also improves nicely. Because this notebook is just for demonstration purposes, we can stop here.
#
# The resulting model of this notebook has been saved to [m3hrdadfi/wav2vec2-xlsr-greek-speech-emotion-recognition](https://huggingface.co/m3hrdadfi/wav2vec2-xlsr-greek-speech-emotion-recognition)
#
# As a final check, let's load the model and verify that it indeed has learned to recognize the emotion in the speech.
#
# Let's first load the pretrained checkpoint.
#
# ## Evaluation
# """
#
# import librosa
# from sklearn.metrics import classification_report
# print(760)
# test_dataset = load_dataset("csv", data_files={"test": "./content/data/test.csv"}, delimiter="\t")["test"]
# test_dataset
#
# device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# print(f"Device: {device}")
#
# model_name_or_path = "m3hrdadfi/wav2vec2-xlsr-greek-speech-emotion-recognition"
# config = AutoConfig.from_pretrained(model_name_or_path)
# processor = Wav2Vec2Processor.from_pretrained(model_name_or_path)
# model = Wav2Vec2ForSpeechClassification.from_pretrained(model_name_or_path).to(device)
#
# def speech_file_to_array_fn(batch):
#     speech_array, sampling_rate = torchaudio.load(batch["path"])
#     speech_array = speech_array.squeeze().numpy()
#     speech_array = librosa.resample(np.asarray(speech_array), sampling_rate, processor.feature_extractor.sampling_rate)
#
#     batch["speech"] = speech_array
#     return batch
#
#
# def predict(batch):
#     features = processor(batch["speech"], sampling_rate=processor.feature_extractor.sampling_rate, return_tensors="pt", padding=True)
#
#     input_values = features.input_values.to(device)
#     attention_mask = features.attention_mask.to(device)
#
#     with torch.no_grad():
#         logits = model(input_values, attention_mask=attention_mask).logits
#
#     pred_ids = torch.argmax(logits, dim=-1).detach().cpu().numpy()
#     batch["predicted"] = pred_ids
#     return batch
#
# test_dataset = test_dataset.map(speech_file_to_array_fn)
#
# result = test_dataset.map(predict, batched=True, batch_size=8)
#
# label_names = [config.id2label[i] for i in range(config.num_labels)]
# label_names
#
# y_true = [config.label2id[name] for name in result["emotion"]]
# y_pred = result["predicted"]
#
# print(y_true[:5])
# print(y_pred[:5])
#
# print(classification_report(y_true, y_pred, target_names=label_names))
#
# """# Prediction"""
#
# import torch
# import torch.nn as nn
# import torch.nn.functional as F
# import torchaudio
# from transformers import AutoConfig, Wav2Vec2Processor
#
# import librosa
# ## import IPython.display as ipd
# import numpy as np
# import pandas as pd
#
# device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# model_name_or_path = "m3hrdadfi/wav2vec2-xlsr-greek-speech-emotion-recognition"
# config = AutoConfig.from_pretrained(model_name_or_path)
# processor = Wav2Vec2Processor.from_pretrained(model_name_or_path)
# sampling_rate = processor.feature_extractor.sampling_rate
# model = Wav2Vec2ForSpeechClassification.from_pretrained(model_name_or_path).to(device)
#
# def speech_file_to_array_fn(path, sampling_rate):
#     speech_array, _sampling_rate = torchaudio.load(path)
#     resampler = torchaudio.transforms.Resample(_sampling_rate)
#     speech = resampler(speech_array).squeeze().numpy()
#     return speech
#
#
# def predict(path, sampling_rate):
#     speech = speech_file_to_array_fn(path, sampling_rate)
#     features = processor(speech, sampling_rate=sampling_rate, return_tensors="pt", padding=True)
#
#     input_values = features.input_values.to(device)
#     attention_mask = features.attention_mask.to(device)
#
#     with torch.no_grad():
#         logits = model(input_values, attention_mask=attention_mask).logits
#
#     scores = F.softmax(logits, dim=1).detach().cpu().numpy()[0]
#     outputs = [{"Emotion": config.id2label[i], "Score": f"{round(score * 100, 3):.1f}%"} for i, score in enumerate(scores)]
#     return outputs
#
#
# STYLES = """
# <style>
# div.display_data {
#     margin: 0 auto;
#     max-width: 500px;
# }
# table.xxx {
#     margin: 50px !important;
#     float: right !important;
#     clear: both !important;
# }
# table.xxx td {
#     min-width: 300px !important;
#     text-align: center !important;
# }
# </style>
# """.strip()
#
# def prediction(df_row):
#     path, emotion = df_row["path"], df_row["emotion"]
#     df = pd.DataFrame([{"Emotion": emotion, "Sentence": "    "}])
#     setup = {
#         'border': 2,
#         'show_dimensions': True,
#         'justify': 'center',
#         'classes': 'xxx',
#         'escape': False,
#     }
#     ## ipd.display(ipd.HTML(STYLES + df.to_html(**setup) + "<br />"))
#     speech, sr = torchaudio.load(path)
#     speech = speech[0].numpy().squeeze()
#     speech = librosa.resample(np.asarray(speech), sr, sampling_rate)
#     ## ipd.display(ipd.Audio(data=np.asarray(speech), autoplay=True, rate=sampling_rate))
#
#     outputs = predict(path, sampling_rate)
#     r = pd.DataFrame(outputs)
#     ## ipd.display(ipd.HTML(STYLES + r.to_html(**setup) + "<br />"))
#
# test = pd.read_csv("./content/data/test.csv", sep="\t")
# test.head()
#
# prediction(test.iloc[0])
#
# prediction(test.iloc[1])
#
# prediction(test.iloc[2])
