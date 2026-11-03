# Sample bills for testing

Use these to try the homeowner journey without a bill of your own: on the **Get solar** page,
upload one at the bill step. All three are **synthetic**. The customers are fictional, and none of
these bills was issued by a real electricity company.

| File | Needs AI keys? | What it shows |
|---|---|---|
| `sample-bill-demo.jpg` | No | A plain synthetic bill. With `AI_MODE=demo` it is read instantly, without any AI call, and labelled as a demo reading. |
| `mahavitaran-style-543-units.jpg` | Yes (`AI_MODE=live`) | A realistic Maharashtra-style bill: one month, six months of history, net amount after a rounding adjustment. |
| `mahavitaran-style-313-units.jpg` | Yes (`AI_MODE=live`) | The same layout for a smaller household. |

## What you should see on "Check your bill"

The app asks the homeowner to confirm figures per month. These are what the live AI read, checked on
2026-11-03:

| File | Average units / month | Bill amount | Fixed charge | Sanctioned load | How the average is worked out |
|---|---|---|---|---|---|
| `sample-bill-demo.jpg` | 340 | ₹3,200 | ₹130 | 3 kW | mean of six months of history |
| `mahavitaran-style-543-units.jpg` | 456.17 | ₹3,842 | ₹120 | 6 kW | mean of six months of history (402 to 543) |
| `mahavitaran-style-313-units.jpg` | 288 | ₹1,964 | ₹100 | 4 kW | mean of six months of history (265 to 313) |

The average uses the printed history, not just the latest month (assumption A-25 in
`docs/ARCHITECTURE.md`): a single hot month shouldn't size a system for the whole year.

## Things worth trying

- **Correct a value before confirming.** The score and suggested size follow what you confirm,
  not what the AI read.
- **Upload a poor photo.** A dark, blurry or very small image is refused before any AI call, with
  the reason and a way to type the values in instead.
- **Run without AI keys.** The live-AI samples then go straight to manual entry, so the journey
  still completes.
- **Free-tier limits.** Groq and Gemini have per-minute and daily caps. If a reading falls back to
  manual entry after heavy testing, that's why.
