# PolyKybd Overlay PNG Specification

Overlay specification so that generated png images can be used with the PolyKybdHost.

## Image layout

- Grid: **10 columns x 9 rows = 90 slots**
- Slot size: **72x40 px** (one per-keycap OLED)
- Image size: **720x360 px**
- Iteration order: row-major (left→right, top→bottom)
- Encoding: **straight (non-premultiplied) RGBA**. Pixels with `A=0` must still carry valid `R`/`G`/`B` bytes — those channels carry the modifier variations independently of alpha.

## File naming and channel-to-modifier mapping

| Filename suffix | Channel R | Channel G | Channel B | Channel A |
|---|---|---|---|---|
| `*.mods.png` (primary) | CTRL | ALT | SHIFT | NO_MOD |
| `*.combo.mods.png` (combo) | CTRL_SHIFT | CTRL_ALT | ALT_SHIFT | GUI_KEY |
| `*.png` (no `.mods.`) | — | — | — | grayscale → NO_MOD |

Each PNG carries up to 4 modifier variations. CTRL_ALT_SHIFT is not supported (see `Modifier` in `polyhost/device/keys.py`); GUI_KEY is loaded but currently dropped before rendering.

## Slot → keycode mapping

Iteration starts at `KC_A` and increments. Two jumps are taken to skip keypad and media ranges (see `ImageConverter.extract_overlays`):

- After slot 79 (`KC_NUM_LOCK` 0x53) → jump to `KC_NONUS_BACKSLASH` 0x64
- After slot 81 (`KC_APPLICATION` 0x65) → jump to `KC_LEFT_CTRL` 0xE0

Resulting 90-slot table:

| Slot | Row | Col | Keycode | Name |
|---:|---:|---:|---|---|
| 0 | 0 | 0 | 0x0004 | `KC_A` |
| 1 | 0 | 1 | 0x0005 | `KC_B` |
| 2 | 0 | 2 | 0x0006 | `KC_C` |
| 3 | 0 | 3 | 0x0007 | `KC_D` |
| 4 | 0 | 4 | 0x0008 | `KC_E` |
| 5 | 0 | 5 | 0x0009 | `KC_F` |
| 6 | 0 | 6 | 0x000a | `KC_G` |
| 7 | 0 | 7 | 0x000b | `KC_H` |
| 8 | 0 | 8 | 0x000c | `KC_I` |
| 9 | 0 | 9 | 0x000d | `KC_J` |
| 10 | 1 | 0 | 0x000e | `KC_K` |
| 11 | 1 | 1 | 0x000f | `KC_L` |
| 12 | 1 | 2 | 0x0010 | `KC_M` |
| 13 | 1 | 3 | 0x0011 | `KC_N` |
| 14 | 1 | 4 | 0x0012 | `KC_O` |
| 15 | 1 | 5 | 0x0013 | `KC_P` |
| 16 | 1 | 6 | 0x0014 | `KC_Q` |
| 17 | 1 | 7 | 0x0015 | `KC_R` |
| 18 | 1 | 8 | 0x0016 | `KC_S` |
| 19 | 1 | 9 | 0x0017 | `KC_T` |
| 20 | 2 | 0 | 0x0018 | `KC_U` |
| 21 | 2 | 1 | 0x0019 | `KC_V` |
| 22 | 2 | 2 | 0x001a | `KC_W` |
| 23 | 2 | 3 | 0x001b | `KC_X` |
| 24 | 2 | 4 | 0x001c | `KC_Y` |
| 25 | 2 | 5 | 0x001d | `KC_Z` |
| 26 | 2 | 6 | 0x001e | `KC_1` |
| 27 | 2 | 7 | 0x001f | `KC_2` |
| 28 | 2 | 8 | 0x0020 | `KC_3` |
| 29 | 2 | 9 | 0x0021 | `KC_4` |
| 30 | 3 | 0 | 0x0022 | `KC_5` |
| 31 | 3 | 1 | 0x0023 | `KC_6` |
| 32 | 3 | 2 | 0x0024 | `KC_7` |
| 33 | 3 | 3 | 0x0025 | `KC_8` |
| 34 | 3 | 4 | 0x0026 | `KC_9` |
| 35 | 3 | 5 | 0x0027 | `KC_0` |
| 36 | 3 | 6 | 0x0028 | `KC_ENTER` |
| 37 | 3 | 7 | 0x0029 | `KC_ESCAPE` |
| 38 | 3 | 8 | 0x002a | `KC_BACKSPACE` |
| 39 | 3 | 9 | 0x002b | `KC_TAB` |
| 40 | 4 | 0 | 0x002c | `KC_SPACE` |
| 41 | 4 | 1 | 0x002d | `KC_MINUS` |
| 42 | 4 | 2 | 0x002e | `KC_EQUAL` |
| 43 | 4 | 3 | 0x002f | `KC_LEFT_BRACKET` |
| 44 | 4 | 4 | 0x0030 | `KC_RIGHT_BRACKET` |
| 45 | 4 | 5 | 0x0031 | `KC_BACKSLASH` |
| 46 | 4 | 6 | 0x0032 | `KC_NONUS_HASH` |
| 47 | 4 | 7 | 0x0033 | `KC_SEMICOLON` |
| 48 | 4 | 8 | 0x0034 | `KC_QUOTE` |
| 49 | 4 | 9 | 0x0035 | `KC_GRAVE` |
| 50 | 5 | 0 | 0x0036 | `KC_COMMA` |
| 51 | 5 | 1 | 0x0037 | `KC_DOT` |
| 52 | 5 | 2 | 0x0038 | `KC_SLASH` |
| 53 | 5 | 3 | 0x0039 | `KC_CAPS_LOCK` |
| 54 | 5 | 4 | 0x003a | `KC_F1` |
| 55 | 5 | 5 | 0x003b | `KC_F2` |
| 56 | 5 | 6 | 0x003c | `KC_F3` |
| 57 | 5 | 7 | 0x003d | `KC_F4` |
| 58 | 5 | 8 | 0x003e | `KC_F5` |
| 59 | 5 | 9 | 0x003f | `KC_F6` |
| 60 | 6 | 0 | 0x0040 | `KC_F7` |
| 61 | 6 | 1 | 0x0041 | `KC_F8` |
| 62 | 6 | 2 | 0x0042 | `KC_F9` |
| 63 | 6 | 3 | 0x0043 | `KC_F10` |
| 64 | 6 | 4 | 0x0044 | `KC_F11` |
| 65 | 6 | 5 | 0x0045 | `KC_F12` |
| 66 | 6 | 6 | 0x0046 | `KC_PRINT_SCREEN` |
| 67 | 6 | 7 | 0x0047 | `KC_SCROLL_LOCK` |
| 68 | 6 | 8 | 0x0048 | `KC_PAUSE` |
| 69 | 6 | 9 | 0x0049 | `KC_INSERT` |
| 70 | 7 | 0 | 0x004a | `KC_HOME` |
| 71 | 7 | 1 | 0x004b | `KC_PAGE_UP` |
| 72 | 7 | 2 | 0x004c | `KC_DELETE` |
| 73 | 7 | 3 | 0x004d | `KC_END` |
| 74 | 7 | 4 | 0x004e | `KC_PAGE_DOWN` |
| 75 | 7 | 5 | 0x004f | `KC_RIGHT` |
| 76 | 7 | 6 | 0x0050 | `KC_LEFT` |
| 77 | 7 | 7 | 0x0051 | `KC_DOWN` |
| 78 | 7 | 8 | 0x0052 | `KC_UP` |
| 79 | 7 | 9 | 0x0053 | `KC_NUM_LOCK` |
| 80 | 8 | 0 | 0x0064 | `KC_NONUS_BACKSLASH` |
| 81 | 8 | 1 | 0x0065 | `KC_APPLICATION` |
| 82 | 8 | 2 | 0x00e0 | `KC_LEFT_CTRL` |
| 83 | 8 | 3 | 0x00e1 | `KC_LEFT_SHIFT` |
| 84 | 8 | 4 | 0x00e2 | `KC_LEFT_ALT` |
| 85 | 8 | 5 | 0x00e3 | `KC_LEFT_GUI` |
| 86 | 8 | 6 | 0x00e4 | `KC_RIGHT_CTRL` |
| 87 | 8 | 7 | 0x00e5 | `KC_RIGHT_SHIFT` |
| 88 | 8 | 8 | 0x00e6 | `KC_RIGHT_ALT` |
| 89 | 8 | 9 | 0x00e7 | `KC_RIGHT_GUI` |

## Test image numbering scheme

Each test image carries `4 x 90 = 360` distinct numbers. Numbers increment **channel-major**: all 90 slots of channel R first, then G, then B, then A. Within a channel the order matches the slot table above. The `--start-number` flag shifts the entire range so a second image can continue without overlap.

- Primary `*.mods.png` (start 0): R/CTRL = 0..89, G/ALT = 90..179, B/SHIFT = 180..269, A/NO_MOD = 270..359
- Combo `*.combo.mods.png` (start 360): R/CTRL_SHIFT = 360..449, G/CTRL_ALT = 450..539, B/ALT_SHIFT = 540..629, A/GUI_KEY = 630..719

### Per-slot manifest (primary image)

| Slot | Keycode | R/CTRL | G/ALT | B/SHIFT | A/NO_MOD |
|---:|---|---:|---:|---:|---:|
| 0 | `KC_A` | 0 | 90 | 180 | 270 |
| 1 | `KC_B` | 1 | 91 | 181 | 271 |
| 2 | `KC_C` | 2 | 92 | 182 | 272 |
| 3 | `KC_D` | 3 | 93 | 183 | 273 |
| 4 | `KC_E` | 4 | 94 | 184 | 274 |
| 5 | `KC_F` | 5 | 95 | 185 | 275 |
| 6 | `KC_G` | 6 | 96 | 186 | 276 |
| 7 | `KC_H` | 7 | 97 | 187 | 277 |
| 8 | `KC_I` | 8 | 98 | 188 | 278 |
| 9 | `KC_J` | 9 | 99 | 189 | 279 |
| 10 | `KC_K` | 10 | 100 | 190 | 280 |
| 11 | `KC_L` | 11 | 101 | 191 | 281 |
| 12 | `KC_M` | 12 | 102 | 192 | 282 |
| 13 | `KC_N` | 13 | 103 | 193 | 283 |
| 14 | `KC_O` | 14 | 104 | 194 | 284 |
| 15 | `KC_P` | 15 | 105 | 195 | 285 |
| 16 | `KC_Q` | 16 | 106 | 196 | 286 |
| 17 | `KC_R` | 17 | 107 | 197 | 287 |
| 18 | `KC_S` | 18 | 108 | 198 | 288 |
| 19 | `KC_T` | 19 | 109 | 199 | 289 |
| 20 | `KC_U` | 20 | 110 | 200 | 290 |
| 21 | `KC_V` | 21 | 111 | 201 | 291 |
| 22 | `KC_W` | 22 | 112 | 202 | 292 |
| 23 | `KC_X` | 23 | 113 | 203 | 293 |
| 24 | `KC_Y` | 24 | 114 | 204 | 294 |
| 25 | `KC_Z` | 25 | 115 | 205 | 295 |
| 26 | `KC_1` | 26 | 116 | 206 | 296 |
| 27 | `KC_2` | 27 | 117 | 207 | 297 |
| 28 | `KC_3` | 28 | 118 | 208 | 298 |
| 29 | `KC_4` | 29 | 119 | 209 | 299 |
| 30 | `KC_5` | 30 | 120 | 210 | 300 |
| 31 | `KC_6` | 31 | 121 | 211 | 301 |
| 32 | `KC_7` | 32 | 122 | 212 | 302 |
| 33 | `KC_8` | 33 | 123 | 213 | 303 |
| 34 | `KC_9` | 34 | 124 | 214 | 304 |
| 35 | `KC_0` | 35 | 125 | 215 | 305 |
| 36 | `KC_ENTER` | 36 | 126 | 216 | 306 |
| 37 | `KC_ESCAPE` | 37 | 127 | 217 | 307 |
| 38 | `KC_BACKSPACE` | 38 | 128 | 218 | 308 |
| 39 | `KC_TAB` | 39 | 129 | 219 | 309 |
| 40 | `KC_SPACE` | 40 | 130 | 220 | 310 |
| 41 | `KC_MINUS` | 41 | 131 | 221 | 311 |
| 42 | `KC_EQUAL` | 42 | 132 | 222 | 312 |
| 43 | `KC_LEFT_BRACKET` | 43 | 133 | 223 | 313 |
| 44 | `KC_RIGHT_BRACKET` | 44 | 134 | 224 | 314 |
| 45 | `KC_BACKSLASH` | 45 | 135 | 225 | 315 |
| 46 | `KC_NONUS_HASH` | 46 | 136 | 226 | 316 |
| 47 | `KC_SEMICOLON` | 47 | 137 | 227 | 317 |
| 48 | `KC_QUOTE` | 48 | 138 | 228 | 318 |
| 49 | `KC_GRAVE` | 49 | 139 | 229 | 319 |
| 50 | `KC_COMMA` | 50 | 140 | 230 | 320 |
| 51 | `KC_DOT` | 51 | 141 | 231 | 321 |
| 52 | `KC_SLASH` | 52 | 142 | 232 | 322 |
| 53 | `KC_CAPS_LOCK` | 53 | 143 | 233 | 323 |
| 54 | `KC_F1` | 54 | 144 | 234 | 324 |
| 55 | `KC_F2` | 55 | 145 | 235 | 325 |
| 56 | `KC_F3` | 56 | 146 | 236 | 326 |
| 57 | `KC_F4` | 57 | 147 | 237 | 327 |
| 58 | `KC_F5` | 58 | 148 | 238 | 328 |
| 59 | `KC_F6` | 59 | 149 | 239 | 329 |
| 60 | `KC_F7` | 60 | 150 | 240 | 330 |
| 61 | `KC_F8` | 61 | 151 | 241 | 331 |
| 62 | `KC_F9` | 62 | 152 | 242 | 332 |
| 63 | `KC_F10` | 63 | 153 | 243 | 333 |
| 64 | `KC_F11` | 64 | 154 | 244 | 334 |
| 65 | `KC_F12` | 65 | 155 | 245 | 335 |
| 66 | `KC_PRINT_SCREEN` | 66 | 156 | 246 | 336 |
| 67 | `KC_SCROLL_LOCK` | 67 | 157 | 247 | 337 |
| 68 | `KC_PAUSE` | 68 | 158 | 248 | 338 |
| 69 | `KC_INSERT` | 69 | 159 | 249 | 339 |
| 70 | `KC_HOME` | 70 | 160 | 250 | 340 |
| 71 | `KC_PAGE_UP` | 71 | 161 | 251 | 341 |
| 72 | `KC_DELETE` | 72 | 162 | 252 | 342 |
| 73 | `KC_END` | 73 | 163 | 253 | 343 |
| 74 | `KC_PAGE_DOWN` | 74 | 164 | 254 | 344 |
| 75 | `KC_RIGHT` | 75 | 165 | 255 | 345 |
| 76 | `KC_LEFT` | 76 | 166 | 256 | 346 |
| 77 | `KC_DOWN` | 77 | 167 | 257 | 347 |
| 78 | `KC_UP` | 78 | 168 | 258 | 348 |
| 79 | `KC_NUM_LOCK` | 79 | 169 | 259 | 349 |
| 80 | `KC_NONUS_BACKSLASH` | 80 | 170 | 260 | 350 |
| 81 | `KC_APPLICATION` | 81 | 171 | 261 | 351 |
| 82 | `KC_LEFT_CTRL` | 82 | 172 | 262 | 352 |
| 83 | `KC_LEFT_SHIFT` | 83 | 173 | 263 | 353 |
| 84 | `KC_LEFT_ALT` | 84 | 174 | 264 | 354 |
| 85 | `KC_LEFT_GUI` | 85 | 175 | 265 | 355 |
| 86 | `KC_RIGHT_CTRL` | 86 | 176 | 266 | 356 |
| 87 | `KC_RIGHT_SHIFT` | 87 | 177 | 267 | 357 |
| 88 | `KC_RIGHT_ALT` | 88 | 178 | 268 | 358 |
| 89 | `KC_RIGHT_GUI` | 89 | 179 | 269 | 359 |

### Per-slot manifest (combo image)

| Slot | Keycode | R/CTRL_SHIFT | G/CTRL_ALT | B/ALT_SHIFT | A/GUI_KEY |
|---:|---|---:|---:|---:|---:|
| 0 | `KC_A` | 360 | 450 | 540 | 630 |
| 1 | `KC_B` | 361 | 451 | 541 | 631 |
| 2 | `KC_C` | 362 | 452 | 542 | 632 |
| 3 | `KC_D` | 363 | 453 | 543 | 633 |
| 4 | `KC_E` | 364 | 454 | 544 | 634 |
| 5 | `KC_F` | 365 | 455 | 545 | 635 |
| 6 | `KC_G` | 366 | 456 | 546 | 636 |
| 7 | `KC_H` | 367 | 457 | 547 | 637 |
| 8 | `KC_I` | 368 | 458 | 548 | 638 |
| 9 | `KC_J` | 369 | 459 | 549 | 639 |
| 10 | `KC_K` | 370 | 460 | 550 | 640 |
| 11 | `KC_L` | 371 | 461 | 551 | 641 |
| 12 | `KC_M` | 372 | 462 | 552 | 642 |
| 13 | `KC_N` | 373 | 463 | 553 | 643 |
| 14 | `KC_O` | 374 | 464 | 554 | 644 |
| 15 | `KC_P` | 375 | 465 | 555 | 645 |
| 16 | `KC_Q` | 376 | 466 | 556 | 646 |
| 17 | `KC_R` | 377 | 467 | 557 | 647 |
| 18 | `KC_S` | 378 | 468 | 558 | 648 |
| 19 | `KC_T` | 379 | 469 | 559 | 649 |
| 20 | `KC_U` | 380 | 470 | 560 | 650 |
| 21 | `KC_V` | 381 | 471 | 561 | 651 |
| 22 | `KC_W` | 382 | 472 | 562 | 652 |
| 23 | `KC_X` | 383 | 473 | 563 | 653 |
| 24 | `KC_Y` | 384 | 474 | 564 | 654 |
| 25 | `KC_Z` | 385 | 475 | 565 | 655 |
| 26 | `KC_1` | 386 | 476 | 566 | 656 |
| 27 | `KC_2` | 387 | 477 | 567 | 657 |
| 28 | `KC_3` | 388 | 478 | 568 | 658 |
| 29 | `KC_4` | 389 | 479 | 569 | 659 |
| 30 | `KC_5` | 390 | 480 | 570 | 660 |
| 31 | `KC_6` | 391 | 481 | 571 | 661 |
| 32 | `KC_7` | 392 | 482 | 572 | 662 |
| 33 | `KC_8` | 393 | 483 | 573 | 663 |
| 34 | `KC_9` | 394 | 484 | 574 | 664 |
| 35 | `KC_0` | 395 | 485 | 575 | 665 |
| 36 | `KC_ENTER` | 396 | 486 | 576 | 666 |
| 37 | `KC_ESCAPE` | 397 | 487 | 577 | 667 |
| 38 | `KC_BACKSPACE` | 398 | 488 | 578 | 668 |
| 39 | `KC_TAB` | 399 | 489 | 579 | 669 |
| 40 | `KC_SPACE` | 400 | 490 | 580 | 670 |
| 41 | `KC_MINUS` | 401 | 491 | 581 | 671 |
| 42 | `KC_EQUAL` | 402 | 492 | 582 | 672 |
| 43 | `KC_LEFT_BRACKET` | 403 | 493 | 583 | 673 |
| 44 | `KC_RIGHT_BRACKET` | 404 | 494 | 584 | 674 |
| 45 | `KC_BACKSLASH` | 405 | 495 | 585 | 675 |
| 46 | `KC_NONUS_HASH` | 406 | 496 | 586 | 676 |
| 47 | `KC_SEMICOLON` | 407 | 497 | 587 | 677 |
| 48 | `KC_QUOTE` | 408 | 498 | 588 | 678 |
| 49 | `KC_GRAVE` | 409 | 499 | 589 | 679 |
| 50 | `KC_COMMA` | 410 | 500 | 590 | 680 |
| 51 | `KC_DOT` | 411 | 501 | 591 | 681 |
| 52 | `KC_SLASH` | 412 | 502 | 592 | 682 |
| 53 | `KC_CAPS_LOCK` | 413 | 503 | 593 | 683 |
| 54 | `KC_F1` | 414 | 504 | 594 | 684 |
| 55 | `KC_F2` | 415 | 505 | 595 | 685 |
| 56 | `KC_F3` | 416 | 506 | 596 | 686 |
| 57 | `KC_F4` | 417 | 507 | 597 | 687 |
| 58 | `KC_F5` | 418 | 508 | 598 | 688 |
| 59 | `KC_F6` | 419 | 509 | 599 | 689 |
| 60 | `KC_F7` | 420 | 510 | 600 | 690 |
| 61 | `KC_F8` | 421 | 511 | 601 | 691 |
| 62 | `KC_F9` | 422 | 512 | 602 | 692 |
| 63 | `KC_F10` | 423 | 513 | 603 | 693 |
| 64 | `KC_F11` | 424 | 514 | 604 | 694 |
| 65 | `KC_F12` | 425 | 515 | 605 | 695 |
| 66 | `KC_PRINT_SCREEN` | 426 | 516 | 606 | 696 |
| 67 | `KC_SCROLL_LOCK` | 427 | 517 | 607 | 697 |
| 68 | `KC_PAUSE` | 428 | 518 | 608 | 698 |
| 69 | `KC_INSERT` | 429 | 519 | 609 | 699 |
| 70 | `KC_HOME` | 430 | 520 | 610 | 700 |
| 71 | `KC_PAGE_UP` | 431 | 521 | 611 | 701 |
| 72 | `KC_DELETE` | 432 | 522 | 612 | 702 |
| 73 | `KC_END` | 433 | 523 | 613 | 703 |
| 74 | `KC_PAGE_DOWN` | 434 | 524 | 614 | 704 |
| 75 | `KC_RIGHT` | 435 | 525 | 615 | 705 |
| 76 | `KC_LEFT` | 436 | 526 | 616 | 706 |
| 77 | `KC_DOWN` | 437 | 527 | 617 | 707 |
| 78 | `KC_UP` | 438 | 528 | 618 | 708 |
| 79 | `KC_NUM_LOCK` | 439 | 529 | 619 | 709 |
| 80 | `KC_NONUS_BACKSLASH` | 440 | 530 | 620 | 710 |
| 81 | `KC_APPLICATION` | 441 | 531 | 621 | 711 |
| 82 | `KC_LEFT_CTRL` | 442 | 532 | 622 | 712 |
| 83 | `KC_LEFT_SHIFT` | 443 | 533 | 623 | 713 |
| 84 | `KC_LEFT_ALT` | 444 | 534 | 624 | 714 |
| 85 | `KC_LEFT_GUI` | 445 | 535 | 625 | 715 |
| 86 | `KC_RIGHT_CTRL` | 446 | 536 | 626 | 716 |
| 87 | `KC_RIGHT_SHIFT` | 447 | 537 | 627 | 717 |
| 88 | `KC_RIGHT_ALT` | 448 | 538 | 628 | 718 |
| 89 | `KC_RIGHT_GUI` | 449 | 539 | 629 | 719 |
