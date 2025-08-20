#!/usr/bin/env python3


def with_bucket_name(func):
    def deco(*original_args, bucket_name=None, **original_kwargs):
        return func(
            *original_args, bucket_name=f"gs://{bucket_name}/", **original_kwargs
        )

    return deco
