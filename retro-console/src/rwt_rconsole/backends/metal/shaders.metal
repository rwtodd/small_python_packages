#include <metal_stdlib>
using namespace metal;

struct Uniforms {
    uint sourceWidth;
    uint sourceHeight;
    uint targetWidth;
    uint targetHeight;
    uint bitDepth;   // 1, 4, or 8
    float scaleX;    // NDC X scale factor for letterboxing
    float scaleY;    // NDC Y scale factor for letterboxing
    uint enableCrt;  // 0 = off, 1 = on
};

struct VertexOut {
    float4 position [[position]];
    float2 uv;
};

vertex VertexOut retro_vertex(
    uint vid [[vertex_id]],
    constant Uniforms& u [[buffer(0)]])
{
    // Quad vertices (2 triangles forming an exact rectangle)
    // Clip space Y: -1 bottom, +1 top. UV Y: 0 top, 1 bottom.
    float2 positions[6] = {
        float2(-1.0, -1.0), // bottom-left
        float2( 1.0, -1.0), // bottom-right
        float2(-1.0,  1.0), // top-left

        float2(-1.0,  1.0), // top-left
        float2( 1.0, -1.0), // bottom-right
        float2( 1.0,  1.0)  // top-right
    };

    float2 uvs[6] = {
        float2(0.0, 1.0), // bottom-left
        float2(1.0, 1.0), // bottom-right
        float2(0.0, 0.0), // top-left

        float2(0.0, 0.0), // top-left
        float2(1.0, 1.0), // bottom-right
        float2(1.0, 0.0)  // top-right
    };

    VertexOut out;
    out.position = float4(positions[vid].x * u.scaleX, positions[vid].y * u.scaleY, 0.0, 1.0);
    out.uv = uvs[vid];
    return out;
}


static inline uint sample_index(
    const device uchar* vram,
    uint sx,
    uint sy,
    uint sourceWidth,
    uint bitDepth)
{
    if (bitDepth == 8u) {
        return uint(vram[sy * sourceWidth + sx]);
    }
    if (bitDepth == 4u) {
        uint pitch = sourceWidth >> 1u;
        uchar b = vram[sy * pitch + (sx >> 1u)];
        return (sx & 1u) == 0u ? uint(b >> 4u) : uint(b & 0x0Fu);
    }
    // 1 bpp
    uint pitch = sourceWidth >> 3u;
    uchar b = vram[sy * pitch + (sx >> 3u)];
    return uint((b >> (7u - (sx & 7u))) & 1u);
}

static inline float2 apply_crt_distortion(float2 uv) {
    float2 cc = uv - 0.5;
    float dist = cc.x * cc.x + cc.y * cc.y;
    cc = cc * (1.0 + dist * 0.08);
    return cc + 0.5;
}

fragment float4 retro_fragment(
    VertexOut in [[stage_in]],
    constant Uniforms& u [[buffer(0)]],
    const device uchar* vram [[buffer(1)]],
    constant float4* palette [[buffer(2)]])
{
    float2 uv = in.uv;

    if (u.enableCrt != 0u) {
        uv = apply_crt_distortion(uv);
        if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
            return float4(0.0, 0.0, 0.0, 1.0); // Black bezel outside tube curvature
        }
    }

    uint sx = min(uint(uv.x * float(u.sourceWidth)), u.sourceWidth - 1u);
    uint sy = min(uint(uv.y * float(u.sourceHeight)), u.sourceHeight - 1u);

    uint colorIndex = sample_index(vram, sx, sy, u.sourceWidth, u.bitDepth);
    float4 color = palette[colorIndex];

    if (u.enableCrt != 0u) {
        // 1. Scanline effect aligned to retro target raster rows
        float scanline = sin(uv.y * float(u.targetHeight) * 3.14159265 * 2.0);
        scanline = 0.5 + 0.5 * scanline;
        float scanlineFactor = mix(0.82, 1.0, scanline);

        // 2. Aperture grille subpixel mask (horizontal R, G, B subpixel simulation)
        float3 mask = float3(1.0);
        int xPos = int(in.position.x) % 3;
        if (xPos == 0) mask = float3(1.04, 0.96, 0.96);
        else if (xPos == 1) mask = float3(0.96, 1.04, 0.96);
        else mask = float3(0.96, 0.96, 1.04);

        // 3. Vignette (gentle corner beam darkening)
        float2 vUV = uv * (1.0 - uv);
        float vign = vUV.x * vUV.y * 15.0;
        vign = clamp(pow(vign, 0.15), 0.0, 1.0);

        color.rgb = clamp(color.rgb * scanlineFactor * mask * vign, 0.0, 1.0);
    }

    return color;
}

