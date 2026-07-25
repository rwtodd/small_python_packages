"""Metal + AppKit retro display window."""

from __future__ import annotations

import sys
import time
from collections.abc import Callable

from rwt_rconsole.display import should_present
from rwt_rconsole.framebuffer import FrameBuffer
from rwt_rconsole.input import MouseButton
from rwt_rconsole.palettes import for_bit_depth
from rwt_rconsole.types import BitDepth, DisplayConfig
from rwt_rconsole.video_math import buffer_length, initial_window_size, palette_length

from .input_map import MetalInput
from .renderer import MetalRenderer
from .surfaces import MetalPalette, MetalVideoBuffer

if sys.platform != "darwin":
    raise ImportError("Metal backend is only available on macOS")


class _AppKitBootstrap:
    _menu_installed = False

    @classmethod
    def ensure_application(cls) -> None:
        from AppKit import NSApplication, NSApplicationActivationPolicyRegular

        NSApplication.sharedApplication()
        app = NSApplication.sharedApplication()
        app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

    @classmethod
    def ensure_main_menu(cls, app_title: str) -> None:
        if cls._menu_installed:
            return
        from AppKit import NSApplication, NSMenu, NSMenuItem

        app = NSApplication.sharedApplication()
        menubar = NSMenu.alloc().init()
        app_menu_item = NSMenuItem.alloc().init()
        menubar.addItem_(app_menu_item)
        app_menu = NSMenu.alloc().initWithTitle_(app_title)
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            f"Quit {app_title}", "terminate:", "q"
        )
        app_menu.addItem_(quit_item)
        app_menu_item.setSubmenu_(app_menu)
        app.setMainMenu_(menubar)
        cls._menu_installed = True


class MetalView:
    """NSView hosting a CAMetalLayer, wired for input."""

    def __init__(self, frame, device, input_ctx: MetalInput):
        from AppKit import (
            NSTrackingArea,
            NSTrackingActiveInKeyWindow,
            NSTrackingInVisibleRect,
            NSTrackingMouseMoved,
            NSView,
            NSViewHeightSizable,
            NSViewWidthSizable,
        )
        from Quartz import CAMetalLayer
        from Metal import MTLPixelFormatBGRA8Unorm
        from Foundation import NSMakeRect

        # Subclass NSView dynamically via objc
        import objc

        parent = self

        class _MetalNSView(NSView):
            def initWithFrame_(self, frame_rect):
                self = objc.super(_MetalNSView, self).initWithFrame_(frame_rect)
                if self is None:
                    return None
                self.wantsLayer = True
                layer = CAMetalLayer.layer()
                layer.setDevice_(device)
                layer.setPixelFormat_(MTLPixelFormatBGRA8Unorm)
                layer.setFramebufferOnly_(True)
                layer.setAllowsNextDrawableTimeout_(True)
                layer.setMaximumDrawableCount_(3)
                layer.setDisplaySyncEnabled_(True)
                self.setLayer_(layer)
                self.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
                self._metal_layer = layer
                self._input = input_ctx
                self._tracking = None
                self._update_drawable_size()
                return self

            def acceptsFirstResponder(self):
                return True

            def metalLayer(self):
                return self._metal_layer

            def _update_drawable_size(self):
                from AppKit import NSScreen
                from Quartz import CGSizeMake

                window = self.window()
                if window is not None:
                    scale = float(window.backingScaleFactor())
                else:
                    scale = float(NSScreen.mainScreen().backingScaleFactor())
                self._metal_layer.setContentsScale_(scale)
                size = self.convertSizeToBacking_(self.bounds().size)
                w = max(float(size.width), 1.0)
                h = max(float(size.height), 1.0)
                self._metal_layer.setDrawableSize_(CGSizeMake(w, h))
                self._metal_layer.setFrame_(self.bounds())
                self._update_tracking()

            def _update_tracking(self):
                from AppKit import (
                    NSTrackingArea,
                    NSTrackingActiveInKeyWindow,
                    NSTrackingInVisibleRect,
                    NSTrackingMouseMoved,
                )

                if self._tracking is not None:
                    self.removeTrackingArea_(self._tracking)
                options = (
                    NSTrackingMouseMoved
                    | NSTrackingActiveInKeyWindow
                    | NSTrackingInVisibleRect
                )
                ta = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                    self.bounds(), options, self, None
                )
                self.addTrackingArea_(ta)
                self._tracking = ta

            def setFrameSize_(self, new_size):
                objc.super(_MetalNSView, self).setFrameSize_(new_size)
                self._update_drawable_size()

            def layout(self):
                objc.super(_MetalNSView, self).layout()
                self._update_drawable_size()

            def viewDidChangeBackingProperties(self):
                # may not exist on all versions; ignore if base doesn't have it
                try:
                    objc.super(_MetalNSView, self).viewDidChangeBackingProperties()
                except Exception:
                    pass
                self._update_drawable_size()

            def _win_pt(self, theEvent):
                bounds = self.bounds()
                pt = self.convertPoint_fromView_(theEvent.locationInWindow(), None)
                view_size = (float(bounds.size.width), float(bounds.size.height))
                win_pt = (float(pt.x), float(bounds.size.height - pt.y))
                return view_size, win_pt

            def keyDown_(self, theEvent):
                chars = theEvent.characters() or ""
                self._input.process_key_down(int(theEvent.keyCode()), chars)

            def keyUp_(self, theEvent):
                self._input.process_key_up(int(theEvent.keyCode()))

            def flagsChanged_(self, theEvent):
                from AppKit import (
                    NSEventModifierFlagShift,
                    NSEventModifierFlagControl,
                    NSEventModifierFlagOption,
                    NSEventModifierFlagCommand,
                    NSEventModifierFlagCapsLock,
                )
                from rwt_rconsole.input import Key
                from .input_map import map_key

                key = map_key(int(theEvent.keyCode()))
                mask = {
                    Key.LEFT_SHIFT: NSEventModifierFlagShift,
                    Key.RIGHT_SHIFT: NSEventModifierFlagShift,
                    Key.LEFT_CTRL: NSEventModifierFlagControl,
                    Key.RIGHT_CTRL: NSEventModifierFlagControl,
                    Key.LEFT_ALT: NSEventModifierFlagOption,
                    Key.RIGHT_ALT: NSEventModifierFlagOption,
                    Key.LEFT_SUPER: NSEventModifierFlagCommand,
                    Key.RIGHT_SUPER: NSEventModifierFlagCommand,
                    Key.CAPS_LOCK: NSEventModifierFlagCapsLock,
                }.get(key)
                self._input.process_flags_changed(
                    int(theEvent.keyCode()), int(theEvent.modifierFlags()), mask
                )

            def mouseDown_(self, theEvent):
                vs, wp = self._win_pt(theEvent)
                self._input.process_mouse_down(MouseButton.LEFT, vs, wp)

            def mouseUp_(self, theEvent):
                vs, wp = self._win_pt(theEvent)
                self._input.process_mouse_up(MouseButton.LEFT, vs, wp)

            def rightMouseDown_(self, theEvent):
                vs, wp = self._win_pt(theEvent)
                self._input.process_mouse_down(MouseButton.RIGHT, vs, wp)

            def rightMouseUp_(self, theEvent):
                vs, wp = self._win_pt(theEvent)
                self._input.process_mouse_up(MouseButton.RIGHT, vs, wp)

            def otherMouseDown_(self, theEvent):
                vs, wp = self._win_pt(theEvent)
                self._input.process_mouse_down(MouseButton.MIDDLE, vs, wp)

            def otherMouseUp_(self, theEvent):
                vs, wp = self._win_pt(theEvent)
                self._input.process_mouse_up(MouseButton.MIDDLE, vs, wp)

            def mouseMoved_(self, theEvent):
                vs, wp = self._win_pt(theEvent)
                self._input.process_mouse_move(vs, wp)

            def mouseDragged_(self, theEvent):
                vs, wp = self._win_pt(theEvent)
                self._input.process_mouse_move(vs, wp)

            def rightMouseDragged_(self, theEvent):
                vs, wp = self._win_pt(theEvent)
                self._input.process_mouse_move(vs, wp)

            def scrollWheel_(self, theEvent):
                self._input.process_scroll(float(theEvent.scrollingDeltaY()))

        from Foundation import NSMakeRect

        # frame may be a tuple (x,y,w,h) or NSRect
        if isinstance(frame, tuple):
            frame_rect = NSMakeRect(*frame)
        else:
            frame_rect = frame

        self._view = _MetalNSView.alloc().initWithFrame_(frame_rect)
        if self._view is None:
            raise RuntimeError("Failed to create MetalView")

    @property
    def nsview(self):
        return self._view

    @property
    def metal_layer(self):
        return self._view.metalLayer()


class MetalRetroDisplay:
    """Metal-backed retro display (1 / 4 / 8 bpp packed VRAM + shared palette)."""

    def __init__(self, config: DisplayConfig) -> None:
        # DisplayConfig validates itself on construction.
        if config.bit_depth not in (BitDepth.BPP1, BitDepth.BPP4, BitDepth.BPP8):
            raise NotImplementedError(f"Unsupported bit depth: {int(config.bit_depth)}")

        from AppKit import (
            NSApplication,
            NSBackingStoreBuffered,
            NSMakeRect,
            NSWindow,
            NSWindowStyleMaskClosable,
            NSWindowStyleMaskMiniaturizable,
            NSWindowStyleMaskResizable,
            NSWindowStyleMaskTitled,
        )
        from Metal import MTLCreateSystemDefaultDevice

        _AppKitBootstrap.ensure_application()
        device = MTLCreateSystemDefaultDevice()
        if device is None:
            raise RuntimeError("No Metal-capable GPU is available.")

        self._config = config
        self._disposed = False
        self._window_closed = False
        self._exiting = False

        vram_len = buffer_length(config.source_size, config.bit_depth)
        self._vram_storage = MetalVideoBuffer(device, vram_len)
        self._fb = FrameBuffer(
            config.source_size, config.bit_depth, data=self._vram_storage
        )
        self._palette = MetalPalette(
            device,
            palette_length(config.bit_depth),
            for_bit_depth(config.bit_depth),
        )
        self._renderer = MetalRenderer(device, config, self._vram_storage, self._palette)
        self._input = MetalInput(config)

        win_size = initial_window_size(config)
        w, h = float(win_size.width), float(win_size.height)

        self._metal_view = MetalView((0.0, 0.0, w, h), device, self._input)
        title = config.title if config.title and config.title.strip() else "RetroConsole"
        _AppKitBootstrap.ensure_main_menu(title)

        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskMiniaturizable
            | NSWindowStyleMaskResizable
        )
        self._window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(100.0, 100.0, w, h),
            style,
            NSBackingStoreBuffered,
            False,
        )
        self._window.setTitle_(config.title)
        self._window.setContentView_(self._metal_view.nsview)
        self._window.setReleasedWhenClosed_(False)

        # WillClose notification
        from Foundation import NSNotificationCenter

        def on_will_close(_notification):
            self._request_exit()

        self._close_observer = (
            NSNotificationCenter.defaultCenter().addObserverForName_object_queue_usingBlock_(
                "NSWindowWillCloseNotification",
                self._window,
                None,
                on_will_close,
            )
        )

        self._window.center()
        self._window.makeKeyAndOrderFront_(None)
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self._renderer.present_layer(self._metal_view.metal_layer)

    def _request_exit(self) -> None:
        if self._exiting:
            return
        self._exiting = True
        self._window_closed = True
        from AppKit import NSApplication, NSEvent, NSEventTypeApplicationDefined
        from Foundation import NSPoint

        app = NSApplication.sharedApplication()
        try:
            app.stop_(app)
        except Exception:
            pass
        try:
            dummy = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
                NSEventTypeApplicationDefined,
                NSPoint(0.0, 0.0),
                0,
                0.0,
                0,
                None,
                0,
                0,
                0,
            )
            if dummy is not None:
                app.postEvent_atStart_(dummy, True)
        except Exception:
            pass

    def _throw_if_disposed(self) -> None:
        if self._disposed:
            raise RuntimeError("MetalRetroDisplay is closed")

    @property
    def config(self) -> DisplayConfig:
        return self._config

    @property
    def buffer(self) -> FrameBuffer:
        return self._fb

    @property
    def palette(self):
        return self._palette

    @property
    def input(self):
        return self._input

    def present(self) -> None:
        self._throw_if_disposed()
        if not self._window_closed:
            self._renderer.present_layer(self._metal_view.metal_layer)

    def run(
        self,
        fps: float,
        on_frame: Callable[["MetalRetroDisplay"], object],
        *,
        cancel: Callable[[], bool] | None = None,
    ) -> None:
        self._throw_if_disposed()
        if fps <= 0.0:
            raise ValueError("fps must be positive.")

        from AppKit import NSApplication, NSTimer

        target_interval = 1.0 / fps
        last_time = [0.0]
        display = self

        def tick(_timer):
            if self._window_closed or (cancel is not None and cancel()):
                self._request_exit()
                return
            now = time.perf_counter()
            if now - last_time[0] >= target_interval - 0.001:
                last_time[0] = now
                self._input.update_frame_state()
                if should_present(on_frame(display)):
                    display.present()

        # Schedule on main run loop
        self._timer = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            min(target_interval, 1.0 / 120.0),
            True,
            tick,
        )
        NSApplication.sharedApplication().run()
        if hasattr(self, "_timer") and self._timer is not None:
            self._timer.invalidate()
            self._timer = None

    def poll_events(self) -> bool:
        self._throw_if_disposed()
        self._input.update_frame_state()
        from AppKit import NSApplication, NSDate, NSEventMaskAny
        from Foundation import NSDefaultRunLoopMode

        app = NSApplication.sharedApplication()
        while True:
            event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                NSEventMaskAny,
                NSDate.distantPast(),
                NSDefaultRunLoopMode,
                True,
            )
            if event is None:
                break
            app.sendEvent_(event)
        return not self._window_closed

    def close(self) -> None:
        if self._disposed:
            return
        self._disposed = True
        self._window_closed = True
        if hasattr(self, "_timer") and self._timer is not None:
            self._timer.invalidate()
            self._timer = None
        try:
            from Foundation import NSNotificationCenter

            if getattr(self, "_close_observer", None) is not None:
                NSNotificationCenter.defaultCenter().removeObserver_(self._close_observer)
        except Exception:
            pass
        try:
            self._window.close()
        except Exception:
            pass

    def __enter__(self) -> MetalRetroDisplay:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class MetalDisplayBackend:
    def create(self, config: DisplayConfig) -> MetalRetroDisplay:
        return MetalRetroDisplay(config)


# Back-compat alias
MetalDisplayFactory = MetalDisplayBackend
