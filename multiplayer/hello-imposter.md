# Hello Imposter Quiz

## Question 1
What happens when you do `arr = [1,2,3]; b = arr`?

- Both variables reference the same list in memory
- A new copy of the list is created for `b`
- Python prevents modification through `b`
- Only the first element is shared between them

Answer: 1
Imposters: 2
Type: single
Time: 30
Explanation: Assignment creates a reference, not a copy. Changes via `b` affect `arr`.

## Question 2
What does `arr * 3` do for a list?

- Repeats the list three times
- Converts all elements to strings
- Extends the list with three new empty elements
- Multiplies each element by 3

Answer: 1
Imposters: 4
Type: single
Time: 30
Explanation: `*` repeats the list, it does not apply multiplication to each element.

## Question 3
What does `arr.append([4,5])` do?

- Adds the list `[4,5]` as a single element
- Adds `4` and `5` as separate elements
- Replaces the last element with `[4,5]`
- Extends the list with `[4,5]`

Answer: 1
Imposters: 2,4
Type: single
Time: 30
Explanation: `append` adds one element, even if that element is a list. Using `extend` would add elements separately.
