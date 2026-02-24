import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.utils.checkpoint as checkpoint

class LayerNorm(nn.Module):
    """ 
    Optimized LayerNorm.
    Uses PyTorch native GroupNorm(1) for "channels_first" which is faster 
    than manual calculation on GPUs.
    """
    def __init__(self, normalized_shape, eps=1e-6, data_format="channels_last"):
        super().__init__()
        self.data_format = data_format
        self.normalized_shape = (normalized_shape, )
        
        if self.data_format == "channels_last":
            self.ln = nn.LayerNorm(normalized_shape, eps=eps)
        elif self.data_format == "channels_first":
            # GroupNorm with groups=1 is mathematically identical to LayerNorm 
            # but optimized for (N, C, D, H, W) layout
            self.gn = nn.GroupNorm(1, normalized_shape, eps=eps)
        else:
            raise NotImplementedError(f"Unsupported data format: {data_format}")
    
    def forward(self, x):
        if self.data_format == "channels_last":
            return self.ln(x)
        else:
            return self.gn(x)

class EPA(nn.Module):
    """
    Efficient Paired Attention Block.
    Now supports dynamic spatial_size to prevent information loss in early layers.
    """
    def __init__(self, dim, num_heads=8, qkv_bias=False, attn_drop=0.0, proj_drop=0.0, spatial_size=7):
        super().__init__()
        self.num_heads = num_heads
        self.temperature = nn.Parameter(torch.ones(num_heads, 1, 1))

        self.qkv = nn.Conv3d(dim, dim * 3, kernel_size=1, bias=qkv_bias)
        
        # DYNAMIC POOLING:
        # Early layers (64x64) need larger pools (e.g., 14) to keep small nodule features.
        # Deep layers (8x8) can use small pools (e.g., 7).
        if isinstance(spatial_size, int):
            spatial_size = (spatial_size, spatial_size, spatial_size)
            
        self.pool_k = nn.AdaptiveAvgPool3d(spatial_size)
        self.pool_v = nn.AdaptiveAvgPool3d(spatial_size)
        
        self.attn_drop = nn.Dropout(attn_drop)
        self.proj = nn.Conv3d(dim, dim, kernel_size=1)
        self.proj_drop = nn.Dropout(proj_drop)

    def forward(self, x):
        B, C, D, H, W = x.shape
        
        qkv = self.qkv(x)
        q, k, v = qkv.chunk(3, dim=1)
        
        # Reshape Q
        q_s = q.view(B, self.num_heads, C // self.num_heads, -1)
        q_s = q_s.permute(0, 1, 3, 2)  # (B, Heads, N, Dim)

        # Pool K and V to fixed size
        k_pooled = self.pool_k(k)
        v_pooled = self.pool_v(v)
        
        k_s = k_pooled.flatten(2).transpose(1, 2) # (B, N_fixed, C)
        v_s = v_pooled.flatten(2).transpose(1, 2) # (B, N_fixed, C)
        
        # Reshape projected K, V for heads
        k_s = k_s.view(B, -1, self.num_heads, C // self.num_heads).permute(0, 2, 1, 3) # (B, Heads, N_fixed, Dim)
        v_s = v_s.view(B, -1, self.num_heads, C // self.num_heads).permute(0, 2, 1, 3) # (B, Heads, N_fixed, Dim)

        # Attention Map
        attn_s = (q_s @ k_s.transpose(-2, -1)) * self.temperature
        attn_s = attn_s.softmax(dim=-1)
        attn_s = self.attn_drop(attn_s)

        x_s = (attn_s @ v_s).permute(0, 1, 3, 2).reshape(B, C, D, H, W)
        
        # --- Channel Branch ---
        q_c = q.mean(dim=(2, 3, 4), keepdim=True) 
        k_c = k.mean(dim=(2, 3, 4), keepdim=True)
        v_c = v 
        
        attn_c = torch.sigmoid(q_c * k_c) 
        x_c = attn_c * v_c 

        # --- Fusion ---
        x = x_s + x_c
        x = self.proj(x)
        x = self.proj_drop(x)
        return x

class UnetrPPBlock(nn.Module):
    def __init__(self, dim, num_heads, proj_drop=0.0, attn_drop=0.0, drop_path=0.0, do_checkpoint=False, spatial_size=7):
        super().__init__()
        self.norm1 = LayerNorm(dim, data_format="channels_first")
        
        # Pass spatial_size to EPA
        self.attn = EPA(
            dim, 
            num_heads=num_heads, 
            qkv_bias=True, 
            attn_drop=attn_drop, 
            proj_drop=proj_drop,
            spatial_size=spatial_size 
        )
        
        self.norm2 = LayerNorm(dim, data_format="channels_first")
        self.mlp = nn.Sequential(
            nn.Conv3d(dim, dim * 4, kernel_size=1),
            nn.GELU(),
            nn.Dropout(proj_drop),
            nn.Conv3d(dim * 4, dim, kernel_size=1),
            nn.Dropout(proj_drop)
        )
        self.drop_path = nn.Identity() 
        self.do_checkpoint = do_checkpoint
        
        # NEW: Learnable Positional Encoding
        # Gives the model spatial awareness (crucial for detection)
        self.pos_embed = nn.Parameter(torch.zeros(1, dim, 1, 1, 1))

    def _forward_impl(self, x):
        # Add PE first
        x = x + self.pos_embed
        x = x + self.drop_path(self.attn(self.norm1(x)))
        x = x + self.drop_path(self.mlp(self.norm2(x)))
        return x

    def forward(self, x):
        if self.do_checkpoint and self.training and x.requires_grad:
            return checkpoint.checkpoint(self._forward_impl, x, use_reentrant=False)
        else:
            return self._forward_impl(x)

class Downsample(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv3d(in_ch, out_ch, kernel_size=3, stride=2, padding=1),
            LayerNorm(out_ch, data_format="channels_first")
        )
    def forward(self, x):
        return self.conv(x)

class Upsample(nn.Module):
    def __init__(self, in_ch, out_ch):
        super().__init__()
        self.conv = nn.Sequential(
            nn.ConvTranspose3d(in_ch, out_ch, kernel_size=2, stride=2),
            LayerNorm(out_ch, data_format="channels_first")
        )
    def forward(self, x):
        return self.conv(x)

class UNETR_PP(nn.Module):
    def __init__(
        self, 
        in_channels=1, 
        out_channels=2, 
        img_size=(128, 128, 128), # Must pass this for Deep Supervision
        base_filters=32, 
        depths=[2, 2, 2, 2], 
        num_heads=[2, 4, 8, 16],
        do_checkpoint=False,
        deep_supervision=True
    ):
        super().__init__()
        self.do_ds = deep_supervision
        self.img_size = img_size
        
        # Patch Partition (Stride 2) -> (B, 32, H/2, W/2, D/2)
        self.patch_embed = nn.Sequential(
            nn.Conv3d(in_channels, base_filters, kernel_size=3, stride=2, padding=1),
            LayerNorm(base_filters, data_format="channels_first")
        )
        
        self.encoders = nn.ModuleList()
        self.downsamples = nn.ModuleList()
        
        current_filter = base_filters
        
        # DYNAMIC POOLING SIZES
        # 0: Resolution 64 -> Pool 14 (Preserves detail)
        # 1: Resolution 32 -> Pool 12
        # 2: Resolution 16 -> Pool 8
        # 3: Resolution 8  -> Pool 7 (Bottleneck)
        pool_sizes = [14, 12, 8, 7]

        # --- Encoders ---
        for i in range(4):
            if i > 0:
                self.downsamples.append(Downsample(current_filter // 2, current_filter))
            
            blocks = nn.Sequential(*[
                UnetrPPBlock(
                    dim=current_filter, 
                    num_heads=num_heads[i], 
                    do_checkpoint=do_checkpoint,
                    spatial_size=pool_sizes[i] # Pass specific pool size
                ) 
                for _ in range(depths[i])
            ])
            self.encoders.append(blocks)
            
            if i < 3: 
                current_filter *= 2

        self.bottleneck = nn.Sequential(*[
            UnetrPPBlock(
                dim=current_filter, 
                num_heads=num_heads[-1], 
                do_checkpoint=do_checkpoint,
                spatial_size=7
            )
            for _ in range(2)
        ])

        self.upsamples = nn.ModuleList()
        self.decoders = nn.ModuleList()
        
        # --- Decoders ---
        # Note: Decoders also need UnetrPPBlocks, we can reuse smaller pool sizes
        # or keep them fixed. For simplicity and speed, we often use fixed 7 or 8 here.
        decoder_pool_size = 7 
        
        for i in range(3, 0, -1):
            upsample = Upsample(current_filter, current_filter // 2)
            self.upsamples.append(upsample)
            
            current_filter = current_filter // 2
            
            fusion = nn.Sequential(
                nn.Conv3d(current_filter * 2, current_filter, kernel_size=3, padding=1),
                LayerNorm(current_filter, data_format="channels_first"),
                nn.GELU()
            )
            
            blocks = nn.Sequential(
                fusion,
                *[UnetrPPBlock(
                    dim=current_filter, 
                    num_heads=num_heads[i-1], 
                    do_checkpoint=do_checkpoint,
                    spatial_size=decoder_pool_size
                  ) 
                  for _ in range(depths[i-1])]
            )
            self.decoders.append(blocks)

        # --- Heads ---
        # Main Head
        self.out_head = nn.Conv3d(base_filters, out_channels, kernel_size=1)
        
        # Auxiliary Heads for Deep Supervision
        if self.do_ds:
            # ROBUSTNESS FIX: Use Upsample(size=img_size) instead of scale_factor
            # This prevents crashes if input crop sizes change.
            
            # DS1: From Decoder 1 (Resolution 32x32x32)
            self.ds1_head = nn.Sequential(
                nn.Conv3d(base_filters * 2, out_channels, kernel_size=1),
                nn.Upsample(size=self.img_size, mode='trilinear', align_corners=False)
            )
            # DS0: From Decoder 0 (Resolution 16x16x16)
            self.ds0_head = nn.Sequential(
                nn.Conv3d(base_filters * 4, out_channels, kernel_size=1),
                nn.Upsample(size=self.img_size, mode='trilinear', align_corners=False)
            )

        # Final Super-Resolution (64 -> 128)
        self.final_up = nn.ConvTranspose3d(out_channels, out_channels, kernel_size=2, stride=2)

    def forward(self, x):
        x_in = x
        x = self.patch_embed(x) 
        
        skips = []
        
        enc0 = self.encoders[0](x)
        skips.append(enc0)
        d1 = self.downsamples[0](enc0)
        enc1 = self.encoders[1](d1)
        skips.append(enc1)
        d2 = self.downsamples[1](enc1)
        enc2 = self.encoders[2](d2)
        skips.append(enc2)
        d3 = self.downsamples[2](enc2)
        enc3 = self.encoders[3](d3)
        
        b = self.bottleneck(enc3)
        
        # Decoder 0
        up0 = self.upsamples[0](b)
        cat0 = torch.cat([up0, skips[2]], dim=1)
        dec0 = self.decoders[0](cat0)
        
        # Decoder 1
        up1 = self.upsamples[1](dec0)
        cat1 = torch.cat([up1, skips[1]], dim=1)
        dec1 = self.decoders[1](cat1)
        
        # Decoder 2
        up2 = self.upsamples[2](dec1)
        cat2 = torch.cat([up2, skips[0]], dim=1)
        dec2 = self.decoders[2](cat2)
        
        logits = self.out_head(dec2) 
        logits = self.final_up(logits) # Main Output (128)
        
        if self.training and self.do_ds:
            # DS heads handle the upsampling to 128 automatically now
            ds1 = self.ds1_head(dec1) 
            ds0 = self.ds0_head(dec0) 
            return [logits, ds1, ds0]
        
        return logits