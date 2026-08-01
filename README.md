# ovos-skill-moviemaster

<img src='PrimaryLogo_Green.png' width='50' style='vertical-align:bottom'/> Movie Master is an OVOS skill that finds information about movies, actors, and production details using [The Movie Database (TMDb)](https://www.themoviedb.org/).

## Examples

- "What is the movie _______ about?"
- "Tell me about the movie _______"
- "Who plays in the movie _______?"
- "What genres does the flick _______ belong to?"
- "Look for information on the movie _______."
- "When was the movie _______ made?"
- "Do you have info on the film _______?"
- "What are popular movies playing now?"
- "What films do you recommend like _______?"
- "How long is the movie _______?"
- "What are the highest rated movies out?"

## Installation

Install the skill with pip:

```
pip install git+https://github.com/OpenVoiceOS/ovos-skill-moviemaster
```

### After installation

Ask a question about a movie, for example "Tell me about the movie Monty Python and the Holy Grail".

The skill ships with a shared TMDb API key. If you hit usage limits, use your own key instead:

1. Sign up for a free account [at TMDb](https://www.themoviedb.org/account/signup).
2. Get an API key [from your TMDb account settings](https://www.themoviedb.org/settings/api). TMDb issues a v3 key and a v4 key. This skill uses the v3 key.
3. Enter the v3 key in your [skill settings file](https://openvoiceos.github.io/community-docs/082-ht_skills_config/) under `apiv3`.

## Category

**Entertainment**

## Tags

#TMDB
#Movies
#Actors

## Related projects

- [OpenVoiceOS/ovos-skill-wikipedia](https://github.com/OpenVoiceOS/ovos-skill-wikipedia) — general knowledge lookups
- [OpenVoiceOS/ovos-skill-pokepedia](https://github.com/OpenVoiceOS/ovos-skill-pokepedia) — another info-lookup skill built the same way

## Credits

This skill uses [tmdbv3api](https://github.com/AnthonyBloomer/tmdbv3api), a Python wrapper for the TMDb API.

It also uses the TMDb API. This skill is not endorsed or certified by TMDb. Information is available [at TMDb](https://www.themoviedb.org/).

## License

Apache-2.0
